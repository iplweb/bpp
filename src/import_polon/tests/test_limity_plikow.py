"""Bezpieczniki rozmiaru pliku importu POLON / absencji."""

from pathlib import Path

import pytest

from import_common.exceptions import DecompressionBombException, PlikZaDuzyException
from import_common.tests._pliki_limity import (
    maly_limit_dekompresji,
    maly_limit_pliku,
    zrob_bombe,
)
from import_polon.forms import validate_polon_headers
from import_polon.utils import read_excel_or_csv_dataframe_guess_encoding

CSV = Path(__file__).parent / "test_import_polon_csv.csv"


def test_csv_za_duzy(monkeypatch):
    maly_limit_pliku(monkeypatch)
    with pytest.raises(PlikZaDuzyException):
        read_excel_or_csv_dataframe_guess_encoding(CSV)


def test_xlsx_bomba(tmp_path, monkeypatch):
    maly_limit_dekompresji(monkeypatch)
    with pytest.raises(DecompressionBombException):
        read_excel_or_csv_dataframe_guess_encoding(zrob_bombe(tmp_path / "b.xlsx"))


def test_walidacja_naglowkow_zwraca_czytelny_blad(tmp_path, monkeypatch):
    maly_limit_dekompresji(monkeypatch)
    bledy = validate_polon_headers(zrob_bombe(tmp_path / "b.xlsx"))
    assert len(bledy) == 1
    assert "dekompresji" in bledy[0]
