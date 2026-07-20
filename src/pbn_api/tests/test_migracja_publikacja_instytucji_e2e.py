"""Prawdziwy ``migrate`` 0077 → 0079 na bazie, która JUŻ zawiera duplikaty.

Ten test nie jest ozdobą: gdyby deduplikacja i ``ADD CONSTRAINT`` siedziały
w JEDNEJ migracji, wywaliłoby się tutaj na ``nie można ALTER TABLE ...
ponieważ posiada oczekujące zdarzenia wyzwalaczy`` (PostgreSQL nie pozwala na
DDL w transakcji, w której ``DELETE`` na tabeli z FK zostawił deferred trigger
events). Testy wołające samą funkcję ``deduplikuj`` tego nie łapią — trzeba
przepuścić prawdziwy ``MigrationExecutor``. Patrz
``test_migracja_dyscypliny_uuid_e2e`` (PR #635) — ten sam mechanizm.
"""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from model_bakery import baker

from pbn_api.models import Institution, Publication, Scientist
from pbn_api.models.publikacja_instytucji import PublikacjaInstytucji

PRZED = ("pbn_api", "0077_constrainty_uuid_dyscyplin")
PO = ("pbn_api", "0079_constraint_publikacja_instytucji")
NAZWA_CONSTRAINTU = "pbn_api_publikacjainstytucji_trojka_unikalna"


def _policz(sql, *params):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone()[0]


@pytest.mark.django_db(transaction=True)
def test_migracja_przechodzi_na_bazie_z_duplikatami():
    # cofnij się PRZED constraint — dopiero wtedy baza wpuści duplikaty
    MigrationExecutor(connection).migrate([PRZED])

    try:
        trojka = {
            "institutionId": baker.make(Institution),
            "publicationId": baker.make(Publication),
            "insPersonId": baker.make(Scientist),
        }
        zostaje = PublikacjaInstytucji.objects.create(**trojka)
        PublikacjaInstytucji.objects.create(**trojka)
        PublikacjaInstytucji.objects.create(**trojka)

        assert PublikacjaInstytucji.objects.filter(**trojka).count() == 3

        # to jest właściwy asert: migracja NIE wywala się na bazie z duplikatami
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([PO])

        assert PublikacjaInstytucji.objects.filter(**trojka).count() == 1
        assert PublikacjaInstytucji.objects.filter(pk=zostaje.pk).exists()
        assert (
            _policz(
                "SELECT count(*) FROM pg_constraint WHERE conname=%s",
                NAZWA_CONSTRAINTU,
            )
            == 1
        )
    finally:
        # Baza MUSI wrócić na docelową migrację (0079) niezależnie od tego,
        # czy powyższe asercje przeszły — inaczej worker testowy zostaje na
        # 0077 (bez constraintu) i psuje WSZYSTKIE kolejne testy w tym
        # procesie kaskadą niezrozumiałych błędów zamiast jednego czytelnego
        # AssertionError z bloku try.
        #
        # Same dane testowe nie wymagają tu ręcznego kasowania: migracja
        # 0078 (RunPython dedup) dedupikuje dowolną liczbę pozostawionych
        # wierszy trójki jako część forward-migrate, więc nie ma osobnego
        # kroku „usuń dane" przed „odtwórz stan", który mógłby rzucić
        # wyjątkiem maskującym oryginalny AssertionError z bloku try.
        MigrationExecutor(connection).migrate([PO])
