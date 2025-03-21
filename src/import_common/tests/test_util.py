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
