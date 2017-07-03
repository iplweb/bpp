# -*- encoding: utf-8 -*-



from mock import Mock
import os

from integrator2.util import find_header_row, build_mapping, read_xls_data


class MockSheet:
    nrows = 5
    ncols = 5

    def row(self, n):
        if n == 4:
            return [Mock(), Mock(), Mock(), Mock(value="test"), Mock()]
        return [Mock(), ] * 5


def test_find_header_row():
    assert find_header_row(MockSheet(), "test") == 4


MOCK_WANTED_COLUMNS = {
    "Tytuł/Stopień": "tytul_skrot",
    "NAZWISKO": "B",
    "IMIĘ": "A",
    "NAZWA JEDNOSTKI": "C",
}


def test_build_mapping():
    xls_columns = [Mock(value="imię"), Mock(value="nazwisko"), Mock(value="NAZWA JEDNOSTKI")]
    wanted_columns = MOCK_WANTED_COLUMNS
    ret = build_mapping(xls_columns, wanted_columns)
    assert ret == ["A", "B", "C"]

def test_build_mapping_alt():
    xls_columns = [Mock(value=x) for x in ['Lp.',
                                           'TYTUŁ CZASOPISMA',
                                           'NR ISSN',
                                           'LICZBA PUNKTÓW ZA PUBLIKACJĘ W CZASOPIŚMIE NAUKOWYM ']]

    wanted_columns = {
                    "TYTUŁ CZASOPISMA": "nazwa",
                    "NR ISSN": "issn",
                    "NR E-ISSN": "e_issn",
                    "LICZBA PUNKTÓW ZA PUBLIKACJĘ W CZASOPIŚMIE NAUKOWYM": "pk"
                }

    ret = build_mapping(xls_columns, wanted_columns)
    assert ret == [None, "nazwa", "issn", "pk"]


def test_read_xls_data():
    gen = read_xls_data(os.path.dirname(__file__) + "/xls/lista_a.xlsx", {"TYTUŁ CZASOPISMA": "fubar"}, "Lp.")
    next(gen)
    next(gen)
    res = next(gen)
    assert res['fubar'] == "AAPG BULLETIN"
