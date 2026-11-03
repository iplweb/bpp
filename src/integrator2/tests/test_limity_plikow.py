"""Bezpieczniki rozmiaru pliku integratora list ministerialnych."""

import os

import pytest

from import_common.exceptions import DecompressionBombException, PlikZaDuzyException
from import_common.tests._pliki_limity import (
    maly_limit_dekompresji,
    maly_limit_pliku,
    zrob_bombe,
)
from integrator2.util import read_xls_data

LISTA_A = os.path.join(os.path.dirname(__file__), "xls", "lista_a.xlsx")


def test_read_xls_data_odrzuca_za_duzy(monkeypatch):
    maly_limit_pliku(monkeypatch)
    with pytest.raises(PlikZaDuzyException):
        next(read_xls_data(LISTA_A, {"TYTUŁ CZASOPISMA": "x"}, "Lp."))


def test_read_xls_data_odrzuca_bombe(tmp_path, monkeypatch):
    maly_limit_dekompresji(monkeypatch)
    with pytest.raises(DecompressionBombException):
        next(read_xls_data(zrob_bombe(tmp_path / "b.xlsx"), {}, "Lp."))
