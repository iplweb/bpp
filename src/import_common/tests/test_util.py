import pytest

from import_common.exceptions import HeaderNotFoundException
from import_common.util import check_if_doi, rename_duplicate_columns, znajdz_naglowek


def test_znajdz_naglowek_dobry(test1_xlsx):
    row, no = znajdz_naglowek(test1_xlsx)
    assert no == 1


def test_znajdz_naglowek_zly(test2_bad_header_xlsx):
    with pytest.raises(HeaderNotFoundException):
        znajdz_naglowek(test2_bad_header_xlsx)


def test_znajdz_naglowek_default(default_xlsx):
    znajdz_naglowek(default_xlsx)


def test_rename_duplicate_columns():
    i = ["issn", "test", "issn", "jeszcze", "raz", "test", "issn"]
    o = ["issn", "test", "issn_2", "jeszcze", "raz", "test_2", "issn_3"]

    assert rename_duplicate_columns(i) == o


@pytest.mark.parametrize("doi,expect", [("10.1002/clc.21018", True)])
def test_check_if_doi(doi, expect):
    assert check_if_doi(doi) == expect


from import_common.util import find_similar_row_in_rows, normalize_cell_header


def test_normalize_cell_header_surowa_wartosc():
    # przyjmuje goły string (nie openpyxl Cell)
    assert normalize_cell_header("Nazwa jednostki") == "nazwa_jednostki"
    # wtrącony \n — bierze tylko PIERWSZĄ linię (wzorzec BPP), reszta odpada
    assert normalize_cell_header("Podstawowe miejsce pracy \nTAK/NIE") == (
        "podstawowe_miejsce_pracy"
    )
    # None → "none" (spójne z dawnym str(elem.value))
    assert normalize_cell_header(None) == "none"


def test_find_similar_row_in_rows_znajduje_naglowek():
    rows = [
        ["Objaśnienie", "", ""],
        ["Nazwisko", "Imię", "Jednostka", "Orcid", "Stanowisko"],
        ["Kowalski", "Jan", "Katedra", "", "Asystent"],
    ]
    res = find_similar_row_in_rows(rows, min_points=3)
    assert res is not None
    kolumny, n = res
    assert n == 2  # 1-based numer wiersza nagłówka
    assert "nazwisko" in kolumny and "jednostka" in kolumny


def test_find_similar_row_in_rows_brak_naglowka():
    rows = [["a", "b"], ["c", "d"]]
    assert find_similar_row_in_rows(rows, min_points=3) is None
