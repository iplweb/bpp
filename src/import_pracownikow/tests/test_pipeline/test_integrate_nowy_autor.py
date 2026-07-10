import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pewnosc import STATUS_BRAK
from import_pracownikow.pipeline.integrate import integruj


def _wiersz_brak(jednostka, utworz_nowego):
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=None,
        jednostka=jednostka,
        confidence=STATUS_BRAK,
        utworz_nowego=utworz_nowego,
        dane_znormalizowane={"nazwisko": "Nowakowski", "imię": "Grzegorz"},
        diff_do_utworzenia={},
        zmiany_potrzebne=False,
    )
    return imp, row


@pytest.mark.django_db
def test_commit_tworzy_nowego_autora(autor_jednostka_fixture):
    _, jednostka = autor_jednostka_fixture
    imp, row = _wiersz_brak(jednostka, utworz_nowego=True)
    p = MockProgress(imp)
    integruj(imp, p)

    row.refresh_from_db()
    assert row.autor is not None
    assert row.autor.nazwisko == "Nowakowski"
    assert row.autor.imiona == "Grzegorz"
    assert Autor_Jednostka.objects.filter(autor=row.autor, jednostka=jednostka).exists()
    assert p.result_context["utworzono_nowych_autorow"] == 1
    assert any("nowy autor" in x for x in row.log_zmian.get("utworzono", []))


@pytest.mark.django_db
def test_commit_pomija_brak_bez_utworz_nowego(autor_jednostka_fixture):
    _, jednostka = autor_jednostka_fixture
    imp, row = _wiersz_brak(jednostka, utworz_nowego=False)
    liczba_przed = Autor.objects.count()
    p = MockProgress(imp)
    integruj(imp, p)

    row.refresh_from_db()
    assert row.autor is None
    assert Autor.objects.count() == liczba_przed
    assert p.result_context["utworzono_nowych_autorow"] == 0
    assert p.result_context["pominieto_niedopasowane"] == 1


@pytest.mark.django_db
def test_commit_nie_tworzy_autora_z_pustym_imieniem(autor_jednostka_fixture):
    """F5: wiersz ``brak`` z ``utworz_nowego=True`` ale pustym ``imię`` (korekta
    na samo nazwisko przez EdytujWierszView, który NIE waliduje imienia) → autor
    NIE powstaje, wiersz zostaje autor=None i liczy się jako niedopasowany."""
    _, jednostka = autor_jednostka_fixture
    imp, row = _wiersz_brak(jednostka, utworz_nowego=True)
    row.dane_znormalizowane = {"nazwisko": "Bezimienny", "imię": ""}
    row.save(update_fields=["dane_znormalizowane"])
    liczba_przed = Autor.objects.count()
    p = MockProgress(imp)
    integruj(imp, p)

    row.refresh_from_db()
    assert row.autor is None
    assert Autor.objects.count() == liczba_przed
    assert p.result_context["utworzono_nowych_autorow"] == 0
    assert p.result_context["pominieto_niedopasowane"] == 1


@pytest.mark.django_db
def test_commit_dedup_tej_samej_osoby_multietat(autor_jednostka_fixture):
    """G4: dwa wiersze ``brak`` tej SAMEJ osoby (identyczne nazwisko/imiona/
    tytuł) w RÓŻNYCH jednostkach, oba ``utworz_nowego=True`` → pre-pass tworzy
    JEDEN ``Autor`` i DWA ``Autor_Jednostka`` (multi-etat), licznik = 1.
    Bez dedupu powstaliby dwaj autorzy-duplikaci."""
    _, jednostka1 = autor_jednostka_fixture
    jednostka2 = baker.make(Jednostka, zarzadzaj_automatycznie=True)
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    dane = {"nazwisko": "Multietatowy", "imię": "Roman"}
    row1 = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=None,
        jednostka=jednostka1,
        confidence=STATUS_BRAK,
        utworz_nowego=True,
        dane_znormalizowane=dane,
        diff_do_utworzenia={},
        zmiany_potrzebne=False,
    )
    row2 = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=None,
        jednostka=jednostka2,
        confidence=STATUS_BRAK,
        utworz_nowego=True,
        dane_znormalizowane=dane,
        diff_do_utworzenia={},
        zmiany_potrzebne=False,
    )
    liczba_przed = Autor.objects.count()
    p = MockProgress(imp)
    integruj(imp, p)

    row1.refresh_from_db()
    row2.refresh_from_db()
    assert row1.autor is not None
    assert row1.autor == row2.autor
    assert Autor.objects.count() == liczba_przed + 1
    assert Autor_Jednostka.objects.filter(autor=row1.autor).count() == 2
    assert p.result_context["utworzono_nowych_autorow"] == 1
