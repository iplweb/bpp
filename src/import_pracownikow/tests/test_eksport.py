from io import BytesIO

import pytest
from model_bakery import baker
from openpyxl import load_workbook

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.eksport import zbuduj_plik_po_imporcie
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.tests._helpers import unikalna_nazwa


def _wczytaj(content):
    ws = load_workbook(BytesIO(content)).active
    naglowki = [c.value for c in ws[1]]
    wiersze = [[c.value for c in row] for row in ws.iter_rows(min_row=2)]
    return naglowki, wiersze


def _import_zintegrowany(**kw):
    return baker.make(
        ImportPracownikow,
        stan=ImportPracownikow.STAN_ZINTEGROWANY,
        mapowanie_kolumn=kw.pop("mapowanie_kolumn", {}),
        **kw,
    )


def _wiersz(imp, *, loc, autor=None, autor_jednostka=None, dane=None):
    return baker.make(
        ImportPracownikowRow,
        parent=imp,
        autor=autor,
        autor_jednostka=autor_jednostka,
        zmiany_potrzebne=False,
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": loc, **(dane or {})},
    )


@pytest.mark.django_db
def test_builder_pomija_wiersze_bez_autora_i_zachowuje_kolejnosc():
    imp = _import_zintegrowany(
        mapowanie_kolumn={
            "Nazwisko": "nazwisko",
            "Imię": "imię",
            "Jednostka": "nazwa_jednostki",
        }
    )
    j = baker.make(Jednostka, nazwa=unikalna_nazwa("Klinika Poprawna"))
    a2 = baker.make(Autor, nazwisko="Druga", imiona="Anna")
    aj2 = baker.make(Autor_Jednostka, autor=a2, jednostka=j)
    a1 = baker.make(Autor, nazwisko="Pierwszy", imiona="Jan")
    aj1 = baker.make(Autor_Jednostka, autor=a1, jednostka=j)
    # loc rosnąco: a1 (loc=0), a2 (loc=1); wiersz pominięty (loc=2, autor=None)
    _wiersz(imp, loc=0, autor=a1, autor_jednostka=aj1)
    _wiersz(imp, loc=1, autor=a2, autor_jednostka=aj2)
    _wiersz(imp, loc=2, autor=None, autor_jednostka=None)

    naglowki, wiersze = _wczytaj(zbuduj_plik_po_imporcie(imp))

    assert len(wiersze) == 2  # pominięty wypadł
    assert naglowki[:4] == ["BPP ID", "Nazwisko", "Imię", "Nazwa jednostki"]
    assert [w[0] for w in wiersze] == [a1.pk, a2.pk]  # kolejność z pliku
    assert [w[1] for w in wiersze] == ["Pierwszy", "Druga"]


@pytest.mark.django_db
def test_ignorowane_kolumny_znikaja_uzyte_zostaja():
    imp = _import_zintegrowany(
        mapowanie_kolumn={
            "Nazwisko": "nazwisko",
            "Imię": "imię",
            "Jedn org": "nazwa_jednostki",
            "Dyscyplina": "__pomin__",  # ignorowana
            "Tytuł nauk.": "tytuł_stopień",  # użyta
        }
    )
    j = baker.make(Jednostka, nazwa=unikalna_nazwa("Katedra X"))
    a = baker.make(Autor, nazwisko="Nowak", imiona="Ewa")
    aj = baker.make(Autor_Jednostka, autor=a, jednostka=j)
    _wiersz(
        imp,
        loc=0,
        autor=a,
        autor_jednostka=aj,
        dane={"Dyscyplina": "nauki medyczne", "Tytuł nauk.": "dr"},
    )

    naglowki, wiersze = _wczytaj(zbuduj_plik_po_imporcie(imp))

    assert "Tytuł" in naglowki
    assert "Stopień służbowy" not in naglowki  # nieużyty target → brak kolumny
    assert "Dyscyplina" not in naglowki
    # Prawdziwa gwarancja: wartość zignorowanej kolumny nie wycieka
    # do ŻADNEJ komórki danych w wyeksportowanym pliku.
    assert not any(
        "nauki medyczne" in str(cell)
        for wiersz in wiersze
        for cell in wiersz
        if cell is not None
    )


@pytest.mark.django_db
def test_wartosc_skorygowana_wygrywa_z_plikiem():
    # Plik miał błędną nazwę jednostki; baza ma poprawną → w pliku wynikowym
    # jest wartość z BAZY.
    imp = _import_zintegrowany(
        mapowanie_kolumn={
            "Nazwisko": "nazwisko",
            "Imię": "imię",
            "Jednostka": "nazwa_jednostki",
        }
    )
    poprawna = unikalna_nazwa("Klinika Chorób Wewnętrznych")
    j = baker.make(Jednostka, nazwa=poprawna)
    a = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    aj = baker.make(Autor_Jednostka, autor=a, jednostka=j)
    _wiersz(
        imp,
        loc=0,
        autor=a,
        autor_jednostka=aj,
        dane={"Jednostka": "klin chor wewn", "Nazwisko": "Kowalksi"},
    )

    naglowki, wiersze = _wczytaj(zbuduj_plik_po_imporcie(imp))

    kol = {n: i for i, n in enumerate(naglowki)}
    assert wiersze[0][kol["Nazwa jednostki"]] == poprawna  # nie "klin chor wewn"
    assert wiersze[0][kol["Nazwisko"]] == "Kowalski"  # nie "Kowalksi"


@pytest.mark.django_db
def test_id_enrich_orcid_gdy_niepusty_mimo_braku_mapowania():
    imp = _import_zintegrowany(
        mapowanie_kolumn={
            "Nazwisko": "nazwisko",
            "Imię": "imię",
            "Jednostka": "nazwa_jednostki",
        }
    )
    j = baker.make(Jednostka, nazwa=unikalna_nazwa("Zakład Y"))
    a = baker.make(Autor, nazwisko="Test", imiona="Orc", orcid="0000-0002-1825-0097")
    aj = baker.make(Autor_Jednostka, autor=a, jednostka=j)
    _wiersz(imp, loc=0, autor=a, autor_jednostka=aj)

    naglowki, wiersze = _wczytaj(zbuduj_plik_po_imporcie(imp))

    assert "ORCID" in naglowki  # niepusty ORCID → kolumna mimo braku w mapowaniu
    kol = {n: i for i, n in enumerate(naglowki)}
    assert wiersze[0][kol["ORCID"]] == "0000-0002-1825-0097"


@pytest.mark.django_db
def test_autor_bez_zatrudnienia_wchodzi_z_pustymi_polami_zatrudnienia():
    imp = _import_zintegrowany(
        mapowanie_kolumn={
            "Nazwisko": "nazwisko",
            "Imię": "imię",
            "Jednostka": "nazwa_jednostki",
            "Etat": "wymiar_etatu_tekst",
        }
    )
    a = baker.make(Autor, nazwisko="Sam", imiona="Autor")
    _wiersz(imp, loc=0, autor=a, autor_jednostka=None)

    naglowki, wiersze = _wczytaj(zbuduj_plik_po_imporcie(imp))

    assert len(wiersze) == 1  # autor wszedł, choć bez zatrudnienia
    kol = {n: i for i, n in enumerate(naglowki)}
    assert wiersze[0][kol["BPP ID"]] == a.pk
    assert wiersze[0][kol["Nazwa jednostki"]] in (None, "")  # AJ None → puste
    assert wiersze[0][kol["Wymiar etatu"]] in (None, "")
