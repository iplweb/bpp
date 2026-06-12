"""Tests for PBN import institution setup helpers."""

import pytest
from model_bakery import baker

from bpp.models import Jednostka, Jednostka_Wydzial, Uczelnia, Wydzial
from pbn_import.models import ImportLog, ImportSession
from pbn_import.utils.institution_import import (
    InstitutionImporter,
    znajdz_lub_utworz_jednostke_domyslna,
    znajdz_lub_utworz_wydzial_domyslny,
    zrob_skrot,
)


@pytest.fixture
def session(db, django_user_model):
    user = baker.make(django_user_model)
    return baker.make(ImportSession, user=user, config={})


@pytest.fixture
def uczelnia(db):
    return baker.make(Uczelnia)


def test_zrob_skrot_keeps_uppercase_and_punctuation_only():
    assert zrob_skrot("Wydział Badań-Aplikacyjnych 2026!") == "WB-A!"


def test_find_or_create_default_wydzial_reuses_uczelnia_scoped_match(uczelnia):
    foreign = baker.make(Wydzial, nazwa="Wydział Domyślny Obcy")
    existing = baker.make(
        Wydzial,
        nazwa="Wydział Domyślny Naukowy",
        uczelnia=uczelnia,
    )

    wydzial, created = znajdz_lub_utworz_wydzial_domyslny(uczelnia)

    assert wydzial == existing
    assert wydzial != foreign
    assert created is False


def test_find_or_create_default_wydzial_creates_with_generated_short_name(uczelnia):
    wydzial, created = znajdz_lub_utworz_wydzial_domyslny(
        uczelnia,
        "Wydział Testów-Jednostkowych",
    )

    assert created is True
    assert wydzial.uczelnia == uczelnia
    assert wydzial.skrot == "WT-J"


def test_find_or_create_default_jednostka_reuses_uczelnia_scoped_match(uczelnia):
    foreign = baker.make(Jednostka, nazwa="Jednostka Domyślna Obca")
    existing = baker.make(
        Jednostka,
        nazwa="Jednostka Domyślna Testowa",
        uczelnia=uczelnia,
    )

    jednostka, created = znajdz_lub_utworz_jednostke_domyslna(uczelnia)

    assert jednostka == existing
    assert jednostka != foreign
    assert created is False


def test_find_or_create_default_jednostka_creates_for_uczelnia(uczelnia):
    jednostka, created = znajdz_lub_utworz_jednostke_domyslna(uczelnia)

    assert created is True
    assert jednostka.nazwa == "Jednostka Domyślna"
    assert jednostka.skrot == "JD"
    assert jednostka.uczelnia == uczelnia


def test_institution_importer_requires_uczelnia(session):
    importer = InstitutionImporter(session, uczelnia=None)

    with pytest.raises(ValueError, match="Nie znaleziono domyślnej Uczelni"):
        importer.run()


def test_institution_importer_creates_defaults_links_and_session_config(
    session,
    uczelnia,
):
    importer = InstitutionImporter(
        session,
        uczelnia=uczelnia,
        wydzial_domyslny="Wydział Testów",
        wydzial_domyslny_skrot="WT",
    )

    result = importer.run()

    session.refresh_from_db()
    uczelnia.refresh_from_db()
    wydzial = result["wydzial"]
    jednostka = result["jednostka"]
    obca_jednostka = result["obca_jednostka"]

    assert wydzial.nazwa == "Wydział Testów"
    assert jednostka.nazwa == "Jednostka Domyślna"
    assert obca_jednostka.nazwa == "Obca jednostka"
    assert obca_jednostka.skupia_pracownikow is False
    assert uczelnia.obca_jednostka == obca_jednostka
    assert Jednostka_Wydzial.objects.filter(
        jednostka=jednostka,
        wydzial=wydzial,
    ).exists()
    assert Jednostka_Wydzial.objects.filter(
        jednostka=obca_jednostka,
        wydzial=wydzial,
    ).exists()
    assert session.config == {
        "default_jednostka_id": jednostka.id,
        "obca_jednostka_id": obca_jednostka.id,
        "wydzial_id": wydzial.id,
    }
    assert ImportLog.objects.filter(session=session, level="info").count() >= 4


def test_institution_importer_reuses_existing_objects(session, uczelnia):
    wydzial = baker.make(Wydzial, nazwa="Wydział Domyślny", uczelnia=uczelnia)
    jednostka = baker.make(Jednostka, nazwa="Jednostka Domyślna", uczelnia=uczelnia)
    obca = baker.make(
        Jednostka,
        nazwa="Obca jednostka",
        uczelnia=uczelnia,
        skupia_pracownikow=False,
    )
    uczelnia.obca_jednostka = obca
    uczelnia.save(update_fields=["obca_jednostka"])
    Jednostka_Wydzial.objects.create(jednostka=jednostka, wydzial=wydzial)
    Jednostka_Wydzial.objects.create(jednostka=obca, wydzial=wydzial)

    result = InstitutionImporter(session, uczelnia=uczelnia).run()

    assert result == {
        "wydzial": wydzial,
        "jednostka": jednostka,
        "obca_jednostka": obca,
    }
    assert Wydzial.objects.filter(uczelnia=uczelnia).count() == 1
    assert Jednostka.objects.filter(uczelnia=uczelnia).count() == 2
    assert ImportLog.objects.filter(
        session=session,
        message__contains="Using existing department",
    ).exists()
