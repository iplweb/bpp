# Create your tests here.
from decimal import Decimal

import pytest

from ewaluacja2021 import const
from ewaluacja2021.tests.utils import curdir
from ewaluacja2021.util import (
    InputXLSX,
    chunker,
    float_or_string_or_int_or_none_to_decimal,
    normalize_xlsx_header_column_name,
)


def test_chunker():
    assert list(
        chunker(
            3,
            [
                [0, 1, 2, 3],
                [0, 1, 2, 3],
                [0, 1, 2, 3],
                [3, 4, 5, 6],
                [3, 4, 5, 6],
                [3, 4, 5],
                [7, 8, 9],
            ],
        )
    ) == [
        ([0, 1, 2, 3], [0, 1, 2, 3], [0, 1, 2, 3]),
        ([3, 4, 5, 6], [3, 4, 5, 6], [3, 4, 5]),
        ([7, 8, 9],),
    ]


@pytest.mark.parametrize(
    "i, o",
    [
        ("łodź_śmierci", "lodz_smierci"),
        ("Lp. ", "lp"),
        ("Jedenaście    milionów", "jedenascie_milionow"),
        (123.123, "123_123"),
    ],
)
def test_normalize_xlsx_header_column_name(i, o):
    assert normalize_xlsx_header_column_name(i) == o


def test_InputXLSX_rows_as_list():
    fn = curdir("test_file.xlsx", __file__)
    i = InputXLSX(fn, const.IMPORT_MAKSYMALNYCH_SLOTOW_COLUMNS)
    ret = list(i.rows_as_list())
    assert "Kowalski" in ret[0]


def test_InputXLSX_rows_as_dict():
    fn = curdir("test_file.xlsx", __file__)
    i = InputXLSX(fn, const.IMPORT_MAKSYMALNYCH_SLOTOW_COLUMNS)
    ret = list(i.rows_as_dict())
    assert ret[0]["nazwisko"] == "Kowalski"
    assert ret[0]["__nrow__"] == 2


@pytest.mark.parametrize(
    "i, o",
    [
        ("3.2", Decimal("3.2")),
        (3.2, Decimal("3.2")),
        (3.12345, Decimal("3.1235")),
        (float(3.2), Decimal("3.2")),
        (None, None),
        (3, Decimal(3)),
    ],
)
def test_float_or_string_or_int_or_none_to_decimal(i, o):
    assert float_or_string_or_int_or_none_to_decimal(i) == o
