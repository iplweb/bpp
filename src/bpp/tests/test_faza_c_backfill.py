"""Faza C / issue #438 — backfill ``poprzednie_nazwy`` (migracja 0466).

PRZED usunięciem modelu ``Wydzial`` dopisujemy nazwę każdego wydziału do
``poprzednie_nazwy`` jego węzła-korzenia (po ``legacy_wydzial_id``), aby
matchowanie importu (``matchuj_wydzial``, T1) dalej odnajdywało root po
dawnej nazwie wydziału — nawet gdy root został PROMOWANY z realnej jednostki
i nosi jej nazwę, a nie nazwę wydziału.
"""

from importlib import import_module

import pytest
from django.apps import apps as global_apps
from model_bakery import baker

from bpp.models import Jednostka, Uczelnia, Wydzial

_mig = import_module("bpp.migrations.0466_faza_c_backfill_poprzednie_nazwy")


@pytest.fixture
def uczelnia(db):
    return baker.make(Uczelnia)


@pytest.mark.django_db
def test_backfill_dopisuje_nazwe_wydzialu_do_promowanego_roota(uczelnia):
    """Root promowany z realnej jednostki nosi jej nazwę — nazwa wydziału
    trafia do ``poprzednie_nazwy``, więc match po dawnej nazwie działa."""
    w = baker.make(Wydzial, nazwa="Wydział Nauk Ścisłych", uczelnia=uczelnia)
    root = baker.make(
        Jednostka,
        uczelnia=uczelnia,
        parent=None,
        nazwa="Katedra Fizyki",
        poprzednie_nazwy="",
        legacy_wydzial_id=w.pk,
    )

    _mig.backfill_poprzednie_nazwy(global_apps, None)

    root.refresh_from_db()
    assert "Wydział Nauk Ścisłych" in root.poprzednie_nazwy


@pytest.mark.django_db
def test_backfill_idempotentny(uczelnia):
    """Dwukrotne uruchomienie nie dubluje wpisu."""
    w = baker.make(Wydzial, nazwa="Wydział Prawa", uczelnia=uczelnia)
    root = baker.make(
        Jednostka,
        uczelnia=uczelnia,
        parent=None,
        nazwa="Instytut Prawa Cywilnego",
        poprzednie_nazwy="",
        legacy_wydzial_id=w.pk,
    )

    _mig.backfill_poprzednie_nazwy(global_apps, None)
    _mig.backfill_poprzednie_nazwy(global_apps, None)

    root.refresh_from_db()
    assert root.poprzednie_nazwy.count("Wydział Prawa") == 1


@pytest.mark.django_db
def test_backfill_pomija_gdy_nazwa_roota_rowna_wydzialowi(uczelnia):
    """Węzeł-lustro (nazwa roota == nazwa wydziału) matchuje po
    ``nazwa__iexact`` — backfill nie musi nic dopisywać."""
    w = baker.make(Wydzial, nazwa="Wydział Lekarski", uczelnia=uczelnia)
    root = baker.make(
        Jednostka,
        uczelnia=uczelnia,
        parent=None,
        nazwa="Wydział Lekarski",
        poprzednie_nazwy="",
        legacy_wydzial_id=w.pk,
    )

    _mig.backfill_poprzednie_nazwy(global_apps, None)

    root.refresh_from_db()
    assert root.poprzednie_nazwy == ""


@pytest.mark.django_db
def test_backfill_pomija_jednostki_bez_legacy_wydzial_id(uczelnia):
    """Zwykła jednostka (bez ``legacy_wydzial_id``) pozostaje nietknięta."""
    j = baker.make(
        Jednostka,
        uczelnia=uczelnia,
        parent=None,
        nazwa="Zwykła Jednostka",
        poprzednie_nazwy="",
        legacy_wydzial_id=None,
    )

    _mig.backfill_poprzednie_nazwy(global_apps, None)

    j.refresh_from_db()
    assert j.poprzednie_nazwy == ""


@pytest.mark.django_db
def test_backfill_zachowuje_istniejace_poprzednie_nazwy(uczelnia):
    """Istniejące ``poprzednie_nazwy`` (np. skopiowane z wydziału) zostają —
    nazwę wydziału DOKŁADAMY, a nie nadpisujemy."""
    w = baker.make(Wydzial, nazwa="Wydział Farmaceutyczny", uczelnia=uczelnia)
    root = baker.make(
        Jednostka,
        uczelnia=uczelnia,
        parent=None,
        nazwa="Kolegium Nauk o Leku",
        poprzednie_nazwy="Dawna Nazwa Historyczna",
        legacy_wydzial_id=w.pk,
    )

    _mig.backfill_poprzednie_nazwy(global_apps, None)

    root.refresh_from_db()
    assert "Dawna Nazwa Historyczna" in root.poprzednie_nazwy
    assert "Wydział Farmaceutyczny" in root.poprzednie_nazwy
