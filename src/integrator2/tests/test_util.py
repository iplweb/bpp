import os
from unittest.mock import Mock

from integrator2.util import build_mapping, find_header_row, read_xls_data


class MockSheet:
    max_row = 5
    max_column = 5

    def iter_rows(self, min_row, max_row):
        BAD_ROW = [
            Mock(),
        ] * 5
        GOOD_ROW = [Mock(), Mock(), Mock(), Mock(value="test"), Mock()]
        for a in range(3):
            yield BAD_ROW
        yield GOOD_ROW
        for a in range(10):
            yield BAD_ROW


def test_find_header_row():
    assert find_header_row(MockSheet(), "test") == 4


MOCK_WANTED_COLUMNS = {
    "Tytuł/Stopień": "tytul_skrot",
    "NAZWISKO": "B",
    "IMIĘ": "A",
    "NAZWA JEDNOSTKI": "C",
}


def test_build_mapping():
    xls_columns = [
        Mock(value="imię"),
        Mock(value="nazwisko"),
        Mock(value="NAZWA JEDNOSTKI"),
    ]
    wanted_columns = MOCK_WANTED_COLUMNS
    ret = build_mapping(xls_columns, wanted_columns)
    assert ret == ["A", "B", "C"]


def test_build_mapping_alt():
    xls_columns = [
        Mock(value=x)
        for x in [
            "Lp.",
            "TYTUŁ CZASOPISMA",
            "NR ISSN",
            "LICZBA PUNKTÓW ZA PUBLIKACJĘ W CZASOPIŚMIE NAUKOWYM ",
        ]
    ]

    wanted_columns = {
        "TYTUŁ CZASOPISMA": "nazwa",
        "NR ISSN": "issn",
        "NR E-ISSN": "e_issn",
        "LICZBA PUNKTÓW ZA PUBLIKACJĘ W CZASOPIŚMIE NAUKOWYM": "pk",
    }

    ret = build_mapping(xls_columns, wanted_columns)
    assert ret == [None, "nazwa", "issn", "pk"]


def test_read_xls_data():
    gen = read_xls_data(
        os.path.dirname(__file__) + "/xls/lista_a.xlsx",
        {"TYTUŁ CZASOPISMA": "fubar"},
        "Lp.",
    )
    next(gen)
    next(gen)
    res = next(gen)
    assert res["fubar"] == "AAPG BULLETIN"
