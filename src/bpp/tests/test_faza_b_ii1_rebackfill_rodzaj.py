"""Faza B (#438), F1 — re-backfill FK ``rodzaj`` z CharField ``rodzaj_jednostki``.

Jednostki utworzone w adminie MIĘDZY Fazą A a B mają ``rodzaj_jednostki``
ustawione (admin edytuje TYLKO CharField), ale ``rodzaj`` (FK) NULL — bo backfill
0451 objął tylko wiersze istniejące w chwili Fazy A. Po II-1 wykluczanie kół z
rankingu idzie po FK (``rodzaj__wyklucz_z_rankingu_autorow``), więc taki drift
CICHO przywraca prace koła do rankingu. Migracja 0459 re-backfilluje FK z
CharField; te testy pilnują, że drift jest domknięty i że re-backfill jest
idempotentny (nie nadpisuje już ustawionego FK).
"""

import importlib

import pytest
from model_bakery import baker

from bpp.models import Jednostka, RodzajJednostki

# Moduł migracji ma nazwę z wiodącą cyfrą — import przez importlib.
_MIGRATION = importlib.import_module("bpp.migrations.0459_faza_b_ii1_retarget")


def _seed_rodzaje():
    """Słownik ``RodzajJednostki`` (seed 0449) — w testach nie jest gwarantowany
    w bazie (baseline), więc go domykamy get-or-create, spójnie z fixture
    ``kolo_naukowe``."""
    standard, _ = RodzajJednostki.objects.get_or_create(
        nazwa="Standard", defaults={"wyklucz_z_rankingu_autorow": False}
    )
    kolo, _ = RodzajJednostki.objects.get_or_create(
        nazwa="Koło naukowe", defaults={"wyklucz_z_rankingu_autorow": True}
    )
    return standard, kolo


@pytest.mark.django_db
def test_rebackfill_rodzaj_domyka_drift_kola(uczelnia):
    from django.apps import apps as global_apps

    _, kolo_rodzaj = _seed_rodzaje()
    # Warunek, po którym ranking wyklucza pracę (patrz ranking_autorow
    # views._apply_exclusions: ``rodzaj__wyklucz_z_rankingu_autorow=True``):
    assert kolo_rodzaj.wyklucz_z_rankingu_autorow is True

    j = baker.make(Jednostka, uczelnia=uczelnia)
    # Symuluj jednostkę utworzoną w adminie po Fazie A: CharField ustawiony,
    # FK ``rodzaj`` NULL. ``update`` omija ewentualną synchronizację w save().
    Jednostka.objects.filter(pk=j.pk).update(
        rodzaj=None, rodzaj_jednostki="kolo_naukowe"
    )
    j.refresh_from_db()
    assert j.rodzaj_id is None  # stan błędu przed re-backfillem

    _MIGRATION.rebackfill_rodzaj_z_charfield(global_apps, None)

    j.refresh_from_db()
    assert j.rodzaj_id == kolo_rodzaj.pk
    # FK teraz spełnia warunek wykluczenia z rankingu autorów:
    assert j.rodzaj.wyklucz_z_rankingu_autorow is True


@pytest.mark.django_db
def test_rebackfill_rodzaj_idempotentny_nie_nadpisuje_istniejacego_fk(uczelnia):
    from django.apps import apps as global_apps

    standard, _ = _seed_rodzaje()

    j = baker.make(Jednostka, uczelnia=uczelnia, rodzaj=standard)
    Jednostka.objects.filter(pk=j.pk).update(rodzaj_jednostki="kolo_naukowe")

    # FK już ustawiony (Standard) — re-backfill NIE może go nadpisać, bo działa
    # WYŁĄCZNIE na wierszach z ``rodzaj_id IS NULL``.
    _MIGRATION.rebackfill_rodzaj_z_charfield(global_apps, None)

    j.refresh_from_db()
    assert j.rodzaj_id == standard.pk


@pytest.mark.django_db
def test_rebackfill_rodzaj_normalna_mapuje_na_standard(uczelnia):
    from django.apps import apps as global_apps

    standard, _ = _seed_rodzaje()

    j = baker.make(Jednostka, uczelnia=uczelnia)
    Jednostka.objects.filter(pk=j.pk).update(rodzaj=None, rodzaj_jednostki="normalna")

    _MIGRATION.rebackfill_rodzaj_z_charfield(global_apps, None)

    j.refresh_from_db()
    assert j.rodzaj_id == standard.pk
