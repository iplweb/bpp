from pathlib import Path

import pytest

from import_polon.utils import read_excel_or_csv_dataframe_guess_encoding


@pytest.mark.parametrize(
    "fn",
    [
        Path(__file__).parent / "test_import_polon_csv.csv",
        Path(__file__).parent / "test_import_polon.xlsx",
    ],
)
def test_read_excel_or_csv_dataframe_guess_encoding(fn):
    res = read_excel_or_csv_dataframe_guess_encoding(fn)
    assert len(res) > 1
