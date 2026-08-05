"""Tests for PBN import institution setup helpers."""

import pytest
from model_bakery import baker

from bpp.models import Jednostka, Jednostka_Rodzic, Uczelnia
from pbn_import.models import ImportLog, ImportSession
from pbn_import.utils.institution_import import (
    InstitutionImporter,
    sprawdz_obca_jednostka,
    znajdz_lub_utworz_jednostke_domyslna,
    znajdz_lub_utworz_obca_jednostke,
    znajdz_lub_utworz_wydzial_domyslny,
    zrob_skrot,
)


@pytest.fixture
def session(db, django_user_model):
    user = baker.make(django_user_model)
    return baker.make(ImportSession, user=user, config={})


@pytest.fixture
def uczelnia(db):
    # Krótki, realistyczny skrót — w multi-hosted nazwy domyślnych jednostek /
    # wydziałów / obcej jednostki sufiksujemy skrótem uczelni (baker domyślnie
    # generuje skrót max-length, co przepełniłoby kolumny po sufiksacji).
    return baker.make(Uczelnia, skrot="UCZ")


def test_zrob_skrot_keeps_uppercase_and_punctuation_only():
    assert zrob_skrot("Wydział Badań-Aplikacyjnych 2026!") == "WB-A!"


def test_find_or_create_default_wydzial_reuses_uczelnia_scoped_match(uczelnia):
    foreign = baker.make(Jednostka, nazwa="Wydział Domyślny Obcy", parent=None)
    existing = baker.make(
        Jednostka,
        nazwa="Wydział Domyślny Naukowy",
        uczelnia=uczelnia,
        parent=None,
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
    assert wydzial.skrot == "WT-J-UCZ"


def test_find_or_create_default_wydzial_create_path_is_uczelnia_unique(db):
    u1 = baker.make(Uczelnia, skrot="UML")
    u2 = baker.make(Uczelnia, skrot="UAFM")

    w1, c1 = znajdz_lub_utworz_wydzial_domyslny(u1)
    w2, c2 = znajdz_lub_utworz_wydzial_domyslny(u2)

    assert c1 is True and c2 is True
    assert w1.nazwa == "Wydział Domyślny UML"
    assert w2.nazwa == "Wydział Domyślny UAFM"
    # Globalnie unikalne nazwa/skrot — drugi create nie może wywalić IntegrityError.
    assert w1.skrot != w2.skrot
    assert w1.skrot == "WD-UML"


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
    assert jednostka.nazwa == "Jednostka Domyślna UCZ"
    assert jednostka.skrot == "JD-UCZ"
    assert jednostka.uczelnia == uczelnia


def test_find_or_create_default_jednostka_create_path_is_uczelnia_unique(db):
    u1 = baker.make(Uczelnia, skrot="UML")
    u2 = baker.make(Uczelnia, skrot="UAFM")

    j1, c1 = znajdz_lub_utworz_jednostke_domyslna(u1)
    j2, c2 = znajdz_lub_utworz_jednostke_domyslna(u2)

    assert c1 is True and c2 is True
    assert j1.nazwa == "Jednostka Domyślna UML"
    assert j2.nazwa == "Jednostka Domyślna UAFM"
    # Globalnie unikalne nazwa/skrot — drugi create nie wywala IntegrityError.
    assert j1.skrot != j2.skrot
    assert j1.skrot == "JD-UML"


def test_obca_jednostka_helper_creates_uczelnia_scoped(uczelnia):
    obca, created = znajdz_lub_utworz_obca_jednostke(uczelnia)
    uczelnia.refresh_from_db()

    assert created is True
    assert obca.nazwa == "Obca jednostka UCZ"
    assert obca.skupia_pracownikow is False
    assert obca.uczelnia == uczelnia
    assert uczelnia.obca_jednostka == obca
    # Bez jawnego `wydzial` helper NIE podpina obcej jednostki do wydziału —
    # obca zostaje czystym węzłem-root (uczelnie bez wydziałów są OK).
    assert not Jednostka_Rodzic.objects.filter(
        jednostka=obca,
        parent__uczelnia=uczelnia,
    ).exists()


def test_obca_jednostka_helper_links_when_wydzial_passed(uczelnia):
    # Ścieżka importera: gdy podamy jawny `wydzial`, helper podpina obcą
    # jednostkę do jego węzła-lustra (zachowana spójność drzewa struktury).
    wydzial, _ = znajdz_lub_utworz_wydzial_domyslny(uczelnia)

    obca, created = znajdz_lub_utworz_obca_jednostke(uczelnia, wydzial=wydzial)

    assert created is True
    assert Jednostka_Rodzic.objects.filter(
        jednostka=obca,
        parent__uczelnia=uczelnia,
    ).exists()


def test_obca_jednostka_helper_is_idempotent(uczelnia):
    first, c1 = znajdz_lub_utworz_obca_jednostke(uczelnia)
    second, c2 = znajdz_lub_utworz_obca_jednostke(uczelnia)

    assert c1 is True
    assert c2 is False
    assert first == second
    assert (
        Jednostka.objects.filter(
            uczelnia=uczelnia,
            skupia_pracownikow=False,
        ).count()
        == 1
    )


def test_obca_jednostka_helper_reuses_existing_fk(uczelnia):
    existing = baker.make(
        Jednostka,
        nazwa="Cokolwiek Obcego",
        uczelnia=uczelnia,
        skupia_pracownikow=False,
    )
    uczelnia.obca_jednostka = existing
    uczelnia.save(update_fields=["obca_jednostka"])

    obca, created = znajdz_lub_utworz_obca_jednostke(uczelnia)

    assert created is False
    assert obca == existing


def test_obca_jednostka_helper_reuses_legacy_by_prefix(uczelnia):
    legacy = baker.make(
        Jednostka,
        nazwa="Obca jednostka",
        uczelnia=uczelnia,
        skupia_pracownikow=False,
    )

    obca, created = znajdz_lub_utworz_obca_jednostke(uczelnia)
    uczelnia.refresh_from_db()

    assert created is False
    assert obca == legacy
    assert uczelnia.obca_jednostka == legacy


def test_obca_jednostka_helper_two_uczelnie_no_collision(db):
    u1 = baker.make(Uczelnia, skrot="UML")
    u2 = baker.make(Uczelnia, skrot="UAFM")

    o1, _ = znajdz_lub_utworz_obca_jednostke(u1)
    o2, _ = znajdz_lub_utworz_obca_jednostke(u2)

    assert o1.nazwa == "Obca jednostka UML"
    assert o2.nazwa == "Obca jednostka UAFM"
    assert o1 != o2


def test_sprawdz_obca_jednostka_ok(uczelnia):
    znajdz_lub_utworz_obca_jednostke(uczelnia)
    uczelnia.refresh_from_db()

    assert sprawdz_obca_jednostka(uczelnia) is None


def test_sprawdz_obca_jednostka_brak_fk(uczelnia):
    problem = sprawdz_obca_jednostka(uczelnia)

    assert problem is not None
    assert "create_obca_jednostka" in problem


def test_sprawdz_obca_jednostka_cudza_uczelnia(uczelnia):
    inna = baker.make(Uczelnia, skrot="INNA")
    obca_innej = baker.make(Jednostka, uczelnia=inna, skupia_pracownikow=False)
    uczelnia.obca_jednostka = obca_innej
    uczelnia.save(update_fields=["obca_jednostka"])

    assert sprawdz_obca_jednostka(uczelnia) is not None


def test_sprawdz_obca_jednostka_skupia_pracownikow(uczelnia):
    # Uczelnia.save() pilnuje invariantu przy zapisie uczelni, ale flaga może
    # zostać przestawiona na samej Jednostce niezależnie (dryf). Walidator musi
    # to wychwycić przed importem.
    obca = baker.make(Jednostka, uczelnia=uczelnia, skupia_pracownikow=False)
    uczelnia.obca_jednostka = obca
    uczelnia.save(update_fields=["obca_jednostka"])
    obca.skupia_pracownikow = True
    obca.save(update_fields=["skupia_pracownikow"])
    uczelnia.refresh_from_db()

    assert sprawdz_obca_jednostka(uczelnia) is not None


def test_sprawdz_obca_jednostka_bez_wydzialu_przechodzi(uczelnia):
    # Uczelnia bez wydziałów: obca jednostka NIE musi być podpięta do wydziału.
    # Wystarczy poprawny FK + sanity (należy do uczelni, skupia_pracownikow=False).
    obca = baker.make(Jednostka, uczelnia=uczelnia, skupia_pracownikow=False)
    uczelnia.obca_jednostka = obca
    uczelnia.save(update_fields=["obca_jednostka"])

    assert sprawdz_obca_jednostka(uczelnia) is None


def test_institution_importer_does_not_collide_with_other_uczelnia_obca(session, db):
    # Uczelnia A już ma globalnie-unikalną "Obca jednostka" (legacy).
    uczelnia_a = baker.make(Uczelnia, skrot="UA")
    baker.make(
        Jednostka,
        nazwa="Obca jednostka",
        skrot="O",
        uczelnia=uczelnia_a,
        skupia_pracownikow=False,
    )

    # Import dla uczelni B nie może trafić w cudzą "Obca jednostka" ani wywalić
    # triggera bpp_jednostka_wydzial_sprawdz_uczelnia_id.
    uczelnia_b = baker.make(Uczelnia, skrot="UB")
    result = InstitutionImporter(session, uczelnia=uczelnia_b).run()

    uczelnia_b.refresh_from_db()
    obca_b = result["obca_jednostka"]
    assert obca_b.uczelnia == uczelnia_b
    assert obca_b.nazwa == "Obca jednostka UB"
    assert uczelnia_b.obca_jednostka == obca_b
    assert Jednostka_Rodzic.objects.filter(
        jednostka=obca_b,
        parent__uczelnia=uczelnia_b,
    ).exists()


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

    assert wydzial.nazwa == "Wydział Testów UCZ"
    assert jednostka.nazwa == "Jednostka Domyślna UCZ"
    assert obca_jednostka.nazwa == "Obca jednostka UCZ"
    assert obca_jednostka.skupia_pracownikow is False
    assert uczelnia.obca_jednostka == obca_jednostka
    assert Jednostka_Rodzic.objects.filter(
        jednostka=jednostka,
        parent=wydzial,
    ).exists()
    assert Jednostka_Rodzic.objects.filter(
        jednostka=obca_jednostka,
        parent=wydzial,
    ).exists()
    assert session.config == {
        "default_jednostka_id": jednostka.id,
        "obca_jednostka_id": obca_jednostka.id,
        "wydzial_id": wydzial.id,
    }
    assert ImportLog.objects.filter(session=session, level="info").count() >= 4


def test_institution_importer_reuses_existing_objects(session, uczelnia):
    wydzial = baker.make(
        Jednostka, nazwa="Wydział Domyślny", uczelnia=uczelnia, parent=None
    )
    jednostka = baker.make(Jednostka, nazwa="Jednostka Domyślna", uczelnia=uczelnia)
    obca = baker.make(
        Jednostka,
        nazwa="Obca jednostka",
        uczelnia=uczelnia,
        skupia_pracownikow=False,
    )
    uczelnia.obca_jednostka = obca
    uczelnia.save(update_fields=["obca_jednostka"])
    Jednostka_Rodzic.objects.create(jednostka=jednostka, parent=wydzial)
    Jednostka_Rodzic.objects.create(jednostka=obca, parent=wydzial)

    result = InstitutionImporter(session, uczelnia=uczelnia).run()

    assert result == {
        "wydzial": wydzial,
        "jednostka": jednostka,
        "obca_jednostka": obca,
    }
    # Faza C (#438): reuse = brak duplikatów. Setup linkuje jednostkę i obcą do
    # wydziału metryczką (Jednostka_Rodzic), bez MPTT-parent, więc wszystkie trzy
    # są tu rootami; kluczowe jest, że run() nie utworzył czwartej jednostki.
    assert Jednostka.objects.filter(uczelnia=uczelnia).count() == 3
    assert ImportLog.objects.filter(
        session=session,
        message__contains="Using existing department",
    ).exists()
