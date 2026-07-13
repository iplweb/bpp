from datetime import date, datetime

import pytest

from import_common.exceptions import XLSMatchError
from import_pracownikow.parsers.wartosci import (
    normalize_date_pl,
    normalizuj_wartosci_wiersza,
    rozbij_nazwisko_imie,
    scal_wymiar_etatu,
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


def _dane(**over):
    d = {"__xls_loc_sheet__": 0, "__xls_loc_row__": 7}
    d.update(over)
    return d


def test_scal_wymiar_zgodne_kanonizuje():
    d = _dane(wymiar_etatu_tekst="1/2 etatu", wymiar_etatu_ulamek="0,5")
    scal_wymiar_etatu(d)
    assert d["wymiar_etatu"] == "0,5"
    assert "wymiar_etatu_tekst" not in d
    assert "wymiar_etatu_ulamek" not in d


def test_scal_wymiar_pelny_etat_zgodny_z_jeden():
    d = _dane(wymiar_etatu_tekst="Pełny etat", wymiar_etatu_ulamek="1")
    scal_wymiar_etatu(d)
    assert d["wymiar_etatu"] == "1"


def test_scal_wymiar_tylko_ulamek():
    d = _dane(wymiar_etatu_ulamek="0,75")
    scal_wymiar_etatu(d)
    assert d["wymiar_etatu"] == "0,75"


def test_scal_wymiar_tylko_tekst():
    d = _dane(wymiar_etatu_tekst="3/4 etatu")
    scal_wymiar_etatu(d)
    assert d["wymiar_etatu"] == "0,75"


def test_scal_wymiar_brak_obu_noop():
    d = _dane(nazwisko="Kowalski")
    scal_wymiar_etatu(d)
    assert "wymiar_etatu" not in d


def test_scal_wymiar_tolerancja_zaokraglenia():
    # 2/3 (0.6667) vs 0,67 — zgodne po zaokrągleniu do 2 miejsc.
    d = _dane(wymiar_etatu_tekst="2/3 etatu", wymiar_etatu_ulamek="0,67")
    scal_wymiar_etatu(d)
    assert d["wymiar_etatu"] == "0,67"


def test_scal_wymiar_rozbieznosc_rzuca():
    d = _dane(wymiar_etatu_tekst="1/2 etatu", wymiar_etatu_ulamek="1")
    with pytest.raises(XLSMatchError):
        scal_wymiar_etatu(d)


def test_scal_wymiar_pojedynczy_niesparsowalny_przechodzi():
    # Pojedyncza kolumna z nieliczbowym wpisem (np. „brak" — legalna wartość
    # słownika) AKCEPTOWANA: przekazana surowo, NIE wywala importu.
    d = _dane(wymiar_etatu_ulamek="brak")
    scal_wymiar_etatu(d)
    assert d["wymiar_etatu"] == "brak"


def test_scal_wymiar_pojedynczy_smiec_tekst_przechodzi():
    d = _dane(wymiar_etatu_tekst="abc")
    scal_wymiar_etatu(d)
    assert d["wymiar_etatu"] == "abc"


def test_scal_wymiar_jedna_kolumna_niesparsowalna_uzywa_drugiej():
    # tekst sparsowalny, ułamek śmieć → używamy sparsowalnego (kanoniczny),
    # bez błędu (nie ma z czym porównać rozbieżności).
    d = _dane(wymiar_etatu_tekst="1/2 etatu", wymiar_etatu_ulamek="brak")
    scal_wymiar_etatu(d)
    assert d["wymiar_etatu"] == "0,5"
