"""Regresja: `StatusGenerowania` z `uczelnia IS NULL` musi być singletonem.

W PostgreSQL NULL-e w indeksie unikalnym są wzajemnie rozróżnialne, więc
`OneToOneField(null=True)` NIE ogranicza liczby wierszy z `uczelnia IS NULL`.
Dwa równoległe żądania mogły utworzyć dwa takie wiersze, a od tej chwili każde
`StatusGenerowania.get_or_create()` (bez argumentu) rzucało
`MultipleObjectsReturned` → trwałe 500 aż do ręcznego sprzątnięcia bazy.
"""

from importlib import import_module

import pytest
from django.apps import apps as django_apps
from django.db import IntegrityError, connection, transaction

from ewaluacja_metryki.models import StatusGenerowania

INDEKS = "ewaluacja_metryki_status_jeden_wiersz_bez_uczelni"


@pytest.mark.django_db
def test_drugi_status_bez_uczelni_odrzucony_przez_baze():
    """Partial unique index dopuszcza co najwyżej jeden wiersz z NULL-em."""
    StatusGenerowania.objects.create(uczelnia=None)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StatusGenerowania.objects.create(uczelnia=None)


@pytest.mark.django_db
def test_get_or_create_bez_argumentu_jest_idempotentne():
    """Powtórzone wywołanie bez argumentu zwraca ten sam wiersz, nie wyjątek."""
    pierwszy = StatusGenerowania.get_or_create()
    drugi = StatusGenerowania.get_or_create()

    assert pierwszy.pk == drugi.pk
    assert StatusGenerowania.objects.filter(uczelnia__isnull=True).count() == 1


@pytest.mark.django_db(transaction=True)
def test_migracja_0010_deduplikuje_istniejace_nulle():
    """Dedup z migracji 0010 zostawia wiersz o najniższym pk.

    Żeby w ogóle dało się odtworzyć stan sprzed naprawy, trzeba na czas testu
    zdjąć indeks założony przez 0011 — potem jest odtwarzany.
    """
    migracja = import_module(
        "ewaluacja_metryki.migrations.0010_dedup_statusgenerowania_bez_uczelni"
    )

    with connection.cursor() as cursor:
        cursor.execute(f"DROP INDEX {INDEKS}")
    try:
        pierwszy = StatusGenerowania.objects.create(uczelnia=None)
        StatusGenerowania.objects.create(uczelnia=None)
        StatusGenerowania.objects.create(uczelnia=None)

        # UWAGA: przekazujemy realny rejestr aplikacji, nie historyczny stan
        # migracji (`django-test-migrations` nie jest zależnością tego repo).
        # Działa, dopóki pola `StatusGenerowania` się nie zmienią — po ich
        # zmianie test zacznie sprawdzać co innego niż robi sama migracja.
        migracja.deduplikuj_statusy_bez_uczelni(django_apps, None)

        assert list(
            StatusGenerowania.objects.filter(uczelnia__isnull=True).values_list(
                "pk", flat=True
            )
        ) == [pierwszy.pk]
    finally:
        # Kolejność ma znaczenie: NAJPIERW czyścimy tabelę, DOPIERO POTEM
        # odtwarzamy indeks. Gdy asercja wyżej padnie przy kilku wierszach
        # z uczelnia IS NULL, `CREATE UNIQUE INDEX` sam rzuciłby IntegrityError
        # wewnątrz `finally` — przesłoniłby prawdziwy AssertionError i zostawił
        # bazę bez indeksu. `pytest.ini` ma `--reuse-db`, więc taka baza
        # przeżyłaby do kolejnych przebiegów i psuła je aż do `--create-db`.
        StatusGenerowania.objects.all().delete()
        # DDL zduplikowany ręcznie względem constraintu z modelu, zakładanego
        # przez migrację 0011 (`AddConstraint` → UniqueConstraint o tej samej
        # nazwie). Po zmianie constraintu w `ewaluacja_metryki.models`
        # ZAKTUALIZUJ też ten SQL — inaczej rozjedzie się po cichu.
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE UNIQUE INDEX {INDEKS} ON ewaluacja_metryki_statusgenerowania "
                "((uczelnia_id IS NULL)) WHERE uczelnia_id IS NULL"
            )
