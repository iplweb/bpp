from unittest.mock import patch

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_common.exceptions import XLSMatchError
from import_pracownikow.models import ImportPracownikow
from import_pracownikow.pewnosc import (
    STATUS_BRAK,
    STATUS_TWARDY,
    STATUS_WIELU,
)
from import_pracownikow.pipeline.analyze import analizuj
from import_pracownikow.tests._helpers import unikalna_nazwa


def _wiersz(**over):
    base = {
        "nazwisko": "Kowalski",
        "imię": "Jan",
        "nazwa_jednostki": "Katedra Testowa",
        "wydział": "Wydział Testowy",
        "__xls_loc_sheet__": 0,
        "__xls_loc_row__": 7,
    }
    base.update(over)
    return base


def _analizuj_jeden(imp, wiersz):
    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MZ:
        MZ.return_value.count.return_value = 1
        MZ.return_value.data.return_value = iter([wiersz])
        analizuj(imp, MockProgress(imp))
    return imp.importpracownikowrow_set.get()


@pytest.mark.django_db
def test_status_twardy_pojedynczy_exact():
    jednostka = baker.make(
        Jednostka,
        nazwa=unikalna_nazwa("Katedra Testowa"),
        skrot=unikalna_nazwa("Kat. T."),
    )
    autor = baker.make(
        Autor, nazwisko="Kowalski", imiona="Jan", aktualna_jednostka=jednostka
    )
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    row = _analizuj_jeden(
        imp, _wiersz(nazwisko="Kowalski", imię="Jan", nazwa_jednostki=jednostka.nazwa)
    )
    assert row.confidence == STATUS_TWARDY
    assert row.autor_id == autor.pk


@pytest.mark.django_db
def test_status_brak_nie_rzuca_i_nie_ustawia_autora():
    nazwa_jed = unikalna_nazwa("Katedra Testowa")
    baker.make(Jednostka, nazwa=nazwa_jed, skrot=unikalna_nazwa("Kat. T."))
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    # nazwisko nie istnieje w bazie → znajdz_kandydatow_autora zwraca []
    row = _analizuj_jeden(
        imp,
        _wiersz(nazwisko="Niematycki", imię="Zdzisław", nazwa_jednostki=nazwa_jed),
    )
    assert row.confidence == STATUS_BRAK
    assert row.autor is None
    assert row.zmiany_potrzebne is False


@pytest.mark.django_db
def test_status_wielu_zapisuje_kandydatow_bez_autora():
    jednostka = baker.make(
        Jednostka,
        nazwa=unikalna_nazwa("Katedra Testowa"),
        skrot=unikalna_nazwa("Kat. T."),
    )
    # DWÓCH autorów o identycznym imieniu+nazwisku → remis na najwyższym tierze
    baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    row = _analizuj_jeden(
        imp, _wiersz(nazwisko="Kowalski", imię="Jan", nazwa_jednostki=jednostka.nazwa)
    )
    assert row.confidence == STATUS_WIELU
    assert row.autor is None
    assert row.zmiany_potrzebne is False
    assert row.kandydaci.count() == 2


@pytest.mark.django_db
def test_status_twardy_po_bpp_id():
    jednostka = baker.make(
        Jednostka,
        nazwa=unikalna_nazwa("Katedra Testowa"),
        skrot=unikalna_nazwa("Kat. T."),
    )
    autor = baker.make(Autor, nazwisko="Zielinski", imiona="Adam")
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    row = _analizuj_jeden(
        imp,
        _wiersz(
            nazwisko="Zielinski",
            imię="Adam",
            nazwa_jednostki=jednostka.nazwa,
            bpp_id=str(autor.pk),
        ),
    )
    assert row.confidence == STATUS_TWARDY
    assert row.autor_id == autor.pk


@pytest.mark.django_db
def test_orcid_nieobecny_nie_wymusza_twardy_przy_remisie():
    # ORCID z pliku NIE istnieje w bazie → ID-path nie rozstrzyga. Dwóch
    # kandydatów po 1.0 w RÓŻNYCH jednostkach → remis top-tier → status WIELU.
    # Regresja F4: gdyby gałąź ID fallbackowała na jednostkę/nazwisko,
    # matchuj_autora rozstrzygnąłby remis jednostką z pliku → błędnie twardy.
    j1 = baker.make(
        Jednostka, nazwa=unikalna_nazwa("Jedn. A"), skrot=unikalna_nazwa("J.A")
    )
    j2 = baker.make(
        Jednostka,
        nazwa=unikalna_nazwa("Katedra Testowa"),
        skrot=unikalna_nazwa("Kat. T."),
    )
    a1 = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    a2 = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    baker.make(Autor_Jednostka, autor=a1, jednostka=j1)
    baker.make(Autor_Jednostka, autor=a2, jednostka=j2)
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    row = _analizuj_jeden(
        imp,
        _wiersz(
            nazwisko="Kowalski",
            imię="Jan",
            nazwa_jednostki=j2.nazwa,
            orcid="0000-0000-0000-9999",
        ),
    )
    assert row.confidence == STATUS_WIELU
    assert row.autor is None
    assert row.kandydaci.count() == 2


@pytest.mark.django_db
def test_konflikt_bpp_id_nadal_rzuca():
    # bpp_id w pliku wskazuje NIEISTNIEJĄCEGO autora, ale nazwisko+imię matchuje
    # kogoś innego → matchuj_autora (ID → None → fallback po nazwisku) zwraca
    # tego autora, a jego pk != bpp_id z pliku → twardy błąd (jak dziś).
    jednostka = baker.make(
        Jednostka,
        nazwa=unikalna_nazwa("Katedra Testowa"),
        skrot=unikalna_nazwa("Kat. T."),
    )
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    nieistniejacy_bpp_id = autor.pk + 999999
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MZ:
        MZ.return_value.count.return_value = 1
        MZ.return_value.data.return_value = iter(
            [
                _wiersz(
                    nazwisko="Kowalski",
                    imię="Jan",
                    nazwa_jednostki=jednostka.nazwa,
                    bpp_id=str(nieistniejacy_bpp_id),
                )
            ]
        )
        with pytest.raises(XLSMatchError):
            analizuj(imp, MockProgress(imp))
