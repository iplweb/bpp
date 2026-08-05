"""Porównywarka „plik vs baza" dla pól zatrudnienia AJ (display-only):
wymiar etatu, grupa pracownicza, podstawowe miejsce pracy — plus komparatory
``_porownaj_fk_obj`` / ``_porownaj_bool`` i bramki ``ma_kolumne_*``."""

import pytest
from model_bakery import baker

from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow

# --- _porownaj_fk_obj (obiekt vs obiekt, po pk) ---------------------------


@pytest.mark.django_db
def test_porownaj_fk_obj_zgodne_gdy_te_same_pk():
    obj = baker.make("bpp.Wymiar_Etatu")
    wynik = ImportPracownikowRow._porownaj_fk_obj(obj, obj)
    assert wynik["rozne"] is False
    assert wynik["plik"] == str(obj)
    assert wynik["baza"] == str(obj)


@pytest.mark.django_db
def test_porownaj_fk_obj_rozne_gdy_inne_pk():
    plik = baker.make("bpp.Wymiar_Etatu")
    baza = baker.make("bpp.Wymiar_Etatu")
    wynik = ImportPracownikowRow._porownaj_fk_obj(plik, baza)
    assert wynik["rozne"] is True
    assert wynik["plik"] == str(plik)
    assert wynik["baza"] == str(baza)


@pytest.mark.django_db
def test_porownaj_fk_obj_rozne_gdy_baza_pusta_a_plik_wskazuje():
    plik = baker.make("bpp.Wymiar_Etatu")
    wynik = ImportPracownikowRow._porownaj_fk_obj(plik, None)
    assert wynik["rozne"] is True
    assert wynik["baza"] == ""


@pytest.mark.django_db
def test_porownaj_fk_obj_niepodswietla_gdy_plik_pusty():
    baza = baker.make("bpp.Wymiar_Etatu")
    wynik = ImportPracownikowRow._porownaj_fk_obj(None, baza)
    assert wynik["rozne"] is False
    assert wynik["plik"] == ""


@pytest.mark.django_db
def test_porownaj_fk_obj_niepodswietla_gdy_brak_bazy_kontekstu():
    plik = baker.make("bpp.Wymiar_Etatu")
    wynik = ImportPracownikowRow._porownaj_fk_obj(plik, None, ma_baze=False)
    assert wynik["rozne"] is False


# --- _porownaj_bool (Tak / Nie / —) --------------------------------------


def test_porownaj_bool_tak_nie_pusto():
    assert ImportPracownikowRow._porownaj_bool(True, True)["plik"] == "Tak"
    assert ImportPracownikowRow._porownaj_bool(False, False)["plik"] == "Nie"
    assert ImportPracownikowRow._porownaj_bool(None, None)["plik"] == ""


def test_porownaj_bool_rozne_gdy_plik_inny_niz_baza():
    wynik = ImportPracownikowRow._porownaj_bool(True, False)
    assert wynik["rozne"] is True
    assert wynik["plik"] == "Tak"
    assert wynik["baza"] == "Nie"


def test_porownaj_bool_zgodne_gdy_takie_same():
    assert ImportPracownikowRow._porownaj_bool(True, True)["rozne"] is False


def test_porownaj_bool_niepodswietla_gdy_plik_none():
    # plik nie mówi nic (None) → to nie różnica, choćby baza miała False.
    assert ImportPracownikowRow._porownaj_bool(None, False)["rozne"] is False


def test_porownaj_bool_niepodswietla_bez_kontekstu_bazy():
    wynik = ImportPracownikowRow._porownaj_bool(True, None, ma_baze=False)
    assert wynik["rozne"] is False


# --- ma_kolumne_* (bramki mapowania) -------------------------------------


@pytest.mark.django_db
def test_ma_kolumne_wymiaru_dla_tekstu_i_ulamka():
    imp = baker.make(
        ImportPracownikow,
        mapowanie_kolumn={"Etat": "wymiar_etatu_tekst"},
    )
    assert imp.ma_kolumne_wymiaru is True
    imp.mapowanie_kolumn = {"Wymiar": "wymiar_etatu_ulamek"}
    assert imp.ma_kolumne_wymiaru is True
    imp.mapowanie_kolumn = {"Coś": "email"}
    assert imp.ma_kolumne_wymiaru is False


@pytest.mark.django_db
def test_ma_kolumne_grupy_i_podstawowego():
    imp = baker.make(
        ImportPracownikow,
        mapowanie_kolumn={
            "Grupa": "grupa_pracownicza",
            "Gł. zakład": "podstawowe_miejsce_pracy",
        },
    )
    assert imp.ma_kolumne_grupy is True
    assert imp.ma_kolumne_podstawowego is True
    imp.mapowanie_kolumn = {}
    assert imp.ma_kolumne_grupy is False
    assert imp.ma_kolumne_podstawowego is False


# --- porownaj_z_baza: wymiar / grupa / podstawowe ------------------------


@pytest.mark.django_db
def test_porownaj_z_baza_wymiar_grupa_podstawowe_rozne():
    autor = baker.make("bpp.Autor")
    jednostka = baker.make("bpp.Jednostka")
    aj = baker.make(
        "bpp.Autor_Jednostka",
        autor=autor,
        jednostka=jednostka,
        wymiar_etatu=baker.make("bpp.Wymiar_Etatu"),
        grupa_pracownicza=baker.make("bpp.Grupa_Pracownicza"),
        podstawowe_miejsce_pracy=False,
    )
    row = baker.make(
        ImportPracownikowRow,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        wymiar_etatu=baker.make("bpp.Wymiar_Etatu"),
        grupa_pracownicza=baker.make("bpp.Grupa_Pracownicza"),
        podstawowe_miejsce_pracy=True,
        dane_znormalizowane={},
    )
    wynik = row.porownaj_z_baza()
    assert wynik["wymiar"]["rozne"] is True
    assert wynik["grupa"]["rozne"] is True
    assert wynik["podstawowe"]["rozne"] is True
    assert wynik["podstawowe"]["plik"] == "Tak"
    assert wynik["podstawowe"]["baza"] == "Nie"


@pytest.mark.django_db
def test_porownaj_z_baza_wymiar_zgodny():
    autor = baker.make("bpp.Autor")
    jednostka = baker.make("bpp.Jednostka")
    wymiar = baker.make("bpp.Wymiar_Etatu")
    aj = baker.make(
        "bpp.Autor_Jednostka",
        autor=autor,
        jednostka=jednostka,
        wymiar_etatu=wymiar,
    )
    row = baker.make(
        ImportPracownikowRow,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        wymiar_etatu=wymiar,
        dane_znormalizowane={},
    )
    assert row.porownaj_z_baza()["wymiar"]["rozne"] is False


@pytest.mark.django_db
def test_porownaj_z_baza_bez_aj_nie_podswietla_zatrudnienia():
    # Wiersz bez autor_jednostka: strona bazy pusta, ma_baze=False → brak
    # fałszywego podświetlenia, choć plik ma wartości.
    row = baker.make(
        ImportPracownikowRow,
        autor=None,
        autor_jednostka=None,
        wymiar_etatu=baker.make("bpp.Wymiar_Etatu"),
        grupa_pracownicza=baker.make("bpp.Grupa_Pracownicza"),
        podstawowe_miejsce_pracy=True,
        dane_znormalizowane={},
    )
    wynik = row.porownaj_z_baza()
    assert wynik["wymiar"]["rozne"] is False
    assert wynik["grupa"]["rozne"] is False
    assert wynik["podstawowe"]["rozne"] is False
    # ale wartość z pliku nadal widoczna:
    assert wynik["podstawowe"]["plik"] == "Tak"
