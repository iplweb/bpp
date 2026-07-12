from datetime import date, datetime

import pytest

from import_pracownikow.parsers.wartosci import (
    normalize_date_pl,
    normalizuj_wartosci_wiersza,
    rozbij_nazwisko_imie,
    sklej_drugie_imie,
)


@pytest.mark.parametrize(
    "wejscie,oczekiwane",
    [
        ("01.10.2016", date(2016, 10, 1)),  # polski DD.MM.YYYY
        ("2016-10-01", "2016-10-01"),  # ISO — zostaw dla ExcelDateField
        (datetime(2016, 10, 1, 12, 0), date(2016, 10, 1)),  # XLSX datetime
        (date(2016, 10, 1), date(2016, 10, 1)),  # date bez zmian
        ("", ""),  # puste — bez zmian
        ("cokolwiek", "cokolwiek"),  # nie-data — bez zmian (form odrzuci)
        (None, None),
    ],
)
def test_normalize_date_pl(wejscie, oczekiwane):
    assert normalize_date_pl(wejscie) == oczekiwane


def test_normalizuj_wartosci_wiersza_tylko_daty():
    elem = {
        "nazwisko": "Kowalski",
        "data_zatrudnienia": "01.10.2016",
        "data_końca_zatrudnienia": "",
        "wymiar_etatu": "1,0",
    }
    out = normalizuj_wartosci_wiersza(elem)
    assert out["data_zatrudnienia"] == date(2016, 10, 1)
    assert out["data_końca_zatrudnienia"] == ""  # puste bez zmian
    assert out["nazwisko"] == "Kowalski"  # nietknięte
    assert out["wymiar_etatu"] == "1,0"  # nie-data nietknięta
    # nie mutuje wejścia
    assert elem["data_zatrudnienia"] == "01.10.2016"


@pytest.mark.parametrize(
    "imie,drugie,oczekiwane",
    [
        ("Jan", "Paweł", "Jan Paweł"),  # oba → scalone spacją
        ("Jan", "", "Jan"),  # puste drugie → imię bez zmian
        ("Jan", None, "Jan"),  # brak drugie → imię bez zmian
        ("", "Paweł", "Paweł"),  # puste imię → samo drugie (wiodąca spacja obcięta)
        (None, "Paweł", "Paweł"),  # brak imię → samo drugie
        ("Jan Anna", "Maria", "Jan Anna Maria"),  # wieloimienne imię + drugie
    ],
)
def test_sklej_drugie_imie(imie, drugie, oczekiwane):
    dane = {"nazwisko": "Kowalski"}
    if imie is not None:
        dane["imię"] = imie
    if drugie is not None:
        dane["drugie_imię"] = drugie

    out = sklej_drugie_imie(dane)

    assert out["imię"] == oczekiwane
    assert "drugie_imię" not in out  # klucz zawsze usunięty (AutorForm go nie zna)
    assert out is dane  # mutuje i zwraca ten sam obiekt
    assert out["nazwisko"] == "Kowalski"  # reszta nietknięta


def test_sklej_drugie_imie_bez_zadnego_klucza_imienia():
    # brak imię i drugie_imię: nic nie dodaje, nie rzuca
    dane = {"nazwisko": "Kowalski"}
    out = sklej_drugie_imie(dane)
    assert "imię" not in out
    assert "drugie_imię" not in out


def test_sklej_drugie_imie_komorka_liczbowa_nie_wybucha():
    # XLSX (openpyxl) potrafi dać liczbę zamiast stringu — .strip() na int
    # rzuciłby AttributeError ubijający analizę; koercja str() to chroni.
    dane = {"imię": "Jan", "drugie_imię": 2}
    out = sklej_drugie_imie(dane)
    assert out["imię"] == "Jan 2"
    assert "drugie_imię" not in out


def test_prosty_split():
    d = rozbij_nazwisko_imie({"nazwisko_imię": "Anszczak Marcin"})
    assert d["nazwisko"] == "Anszczak"
    assert d["imię"] == "Marcin"
    assert "nazwisko_imię" not in d


def test_nazwisko_z_lacznikiem():
    d = rozbij_nazwisko_imie({"nazwisko_imię": "Ciuka-Witrylak Małgorzata"})
    assert d["nazwisko"] == "Ciuka-Witrylak"
    assert d["imię"] == "Małgorzata"


def test_nie_nadpisuje_istniejacych():
    d = rozbij_nazwisko_imie(
        {"nazwisko_imię": "Anszczak Marcin", "nazwisko": "X", "imię": "Y"}
    )
    assert d["nazwisko"] == "X"
    assert d["imię"] == "Y"


def test_brak_klucza_no_op():
    d = rozbij_nazwisko_imie({"nazwisko": "Kowalski"})
    assert d == {"nazwisko": "Kowalski"}
