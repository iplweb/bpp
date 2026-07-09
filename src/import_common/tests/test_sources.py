import pytest

from import_common.exceptions import HeaderNotFoundException
from import_common.sources import CSVSource, XLSXSource, wykryj_format


def test_wykryj_format_xlsx_po_magic_bytes(test1_xlsx):
    # XLSX = archiwum ZIP, zaczyna się od b"PK"
    assert wykryj_format(test1_xlsx) == "xlsx"


def test_wykryj_format_csv_gdy_nie_zip(tmp_path):
    p = tmp_path / "dane.csv"
    p.write_text("Nazwisko;Imię\nKowalski;Jan\n", encoding="utf-8")
    assert wykryj_format(str(p)) == "csv"


def test_xlsxsource_deleguje_do_xlsimportfile(default_xlsx):
    src = XLSXSource(default_xlsx)
    # count() i data() zwracają to samo, co XLSImportFile
    assert src.count() >= 0
    wiersze = list(src.data())
    assert len(wiersze) == src.count()
    if wiersze:
        # kontrakt kluczy lokalizacyjnych
        assert "__xls_loc_sheet__" in wiersze[0]
        assert "__xls_loc_row__" in wiersze[0]


_CSV_NAGLOWEK = "Numer;Nazwisko;Imię;Orcid;Stanowisko;Nazwa jednostki"


def _zapisz(tmp_path, tresc, encoding="utf-8", nazwa="dane.csv"):
    p = tmp_path / nazwa
    p.write_bytes(tresc.encode(encoding))
    return str(p)


def test_csvsource_srednik_cp1250(tmp_path):
    tresc = (
        f"{_CSV_NAGLOWEK}\n"
        "1;Kowalski;Jan;;Asystent;Katedra Chorób\n"
        "2;Wiśniewska;Zofia;;Adiunkt;Zakład Fizyki\n"
    )
    path = _zapisz(tmp_path, tresc, encoding="cp1250")
    src = CSVSource(path)
    assert src.count() == 2
    wiersze = list(src.data())
    assert wiersze[0]["nazwisko"] == "Kowalski"
    assert wiersze[0]["nazwa_jednostki"] == "Katedra Chorób"
    # klucze lokalizacyjne — CSV to jeden arkusz
    assert wiersze[0]["__xls_loc_sheet__"] == 0
    assert wiersze[1]["__xls_loc_row__"] > wiersze[0]["__xls_loc_row__"]


def test_csvsource_przecinek_delimiter(tmp_path):
    tresc = (
        "Nazwisko,Imię,Nazwa jednostki,Orcid,Stanowisko\n"
        "Nowak,Anna,Katedra Testowa,,Profesor\n"
    )
    path = _zapisz(tmp_path, tresc, encoding="utf-8")
    src = CSVSource(path)
    assert src.count() == 1
    assert list(src.data())[0]["imię"] == "Anna"


def test_csvsource_odrzuca_pesel(tmp_path):
    tresc = (
        "Nazwisko;Imię;PESEL;Nazwa jednostki;Orcid;Stanowisko\n"
        "Kowalski;Jan;12345678901;Katedra;;Asystent\n"
    )
    path = _zapisz(tmp_path, tresc, encoding="utf-8")
    wiersz = list(CSVSource(path).data())[0]
    assert "pesel" not in wiersz


def test_csvsource_brak_naglowka_rzuca(tmp_path):
    tresc = "aaa;bbb;ccc\n1;2;3\n"
    path = _zapisz(tmp_path, tresc, encoding="utf-8")
    with pytest.raises(HeaderNotFoundException):
        CSVSource(path).count()


def test_csvsource_pusty_plik_zero(tmp_path):
    # sam nagłówek, brak danych
    tresc = f"{_CSV_NAGLOWEK}\n"
    path = _zapisz(tmp_path, tresc, encoding="utf-8")
    src = CSVSource(path)
    assert src.count() == 0
    assert list(src.data()) == []


def test_csvsource_pomija_puste_linie(tmp_path):
    tresc = (
        f"{_CSV_NAGLOWEK}\n"
        "1;Kowalski;Jan;;Asystent;Katedra\n"
        "\n"
        ";;;;;\n"
        "2;Nowak;Ewa;;Adiunkt;Zakład\n"
    )
    path = _zapisz(tmp_path, tresc, encoding="utf-8")
    src = CSVSource(path)
    assert src.count() == 2


def test_csvsource_poszarpany_wiersz_zachowuje_loc_keys(tmp_path):
    # wiersz danych KRÓTSZY niż nagłówek (csv.reader nie padduje) — klucze
    # lokalizacyjne muszą i tak powstać na właściwych pozycjach
    tresc = f"{_CSV_NAGLOWEK}\n" "1;Kowalski;Jan\n"  # brak 3 ostatnich kolumn
    path = _zapisz(tmp_path, tresc, encoding="utf-8")
    wiersz = list(CSVSource(path).data())[0]
    assert wiersz["__xls_loc_sheet__"] == 0
    assert wiersz["__xls_loc_row__"] == 1
    assert wiersz["nazwisko"] == "Kowalski"
    # brakujące kolumny → puste, nie przesunięte
    assert wiersz["nazwa_jednostki"] == ""


def test_csvsource_srednik_wygrywa_z_przecinkiem_dziesietnym(tmp_path):
    # §13: plik `;` z przecinkiem dziesiętnym `0,5` w komórce — detekcja NIE
    # może wybrać `,` jako delimitera; komórka „0,5" zostaje w całości
    tresc = (
        "Nazwisko;Imię;Nazwa jednostki;Orcid;Stanowisko;Wymiar etatu\n"
        "Kowalski;Jan;Katedra;;Asystent;0,5\n"
        "Nowak;Ewa;Zakład;;Adiunkt;0,5\n"
    )
    path = _zapisz(tmp_path, tresc, encoding="utf-8")
    src = CSVSource(path)
    assert src.count() == 2
    wiersz = list(src.data())[0]
    assert wiersz["wymiar_etatu"] == "0,5"
    assert wiersz["nazwisko"] == "Kowalski"
