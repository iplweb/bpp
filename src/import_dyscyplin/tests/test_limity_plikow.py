"""Bezpieczniki rozmiaru pliku importu dyscyplin."""

import pytest

from import_common.exceptions import DecompressionBombException, PlikZaDuzyException
from import_common.tests._pliki_limity import (
    maly_limit_dekompresji,
    maly_limit_pliku,
    zrob_bombe,
)
from import_dyscyplin.core import przeanalizuj_plik_xls


def test_przeanalizuj_odrzuca_za_duzy(test1_xlsx, monkeypatch):
    maly_limit_pliku(monkeypatch)
    with pytest.raises(PlikZaDuzyException):
        przeanalizuj_plik_xls(test1_xlsx, parent=None)


def test_przeanalizuj_odrzuca_bombe(tmp_path, monkeypatch):
    maly_limit_dekompresji(monkeypatch)
    with pytest.raises(DecompressionBombException):
        przeanalizuj_plik_xls(zrob_bombe(tmp_path / "b.xlsx"), parent=None)


def test_stworz_kolumny_bomba_czytelny_blad(import_dyscyplin, tmp_path, monkeypatch):
    maly_limit_dekompresji(monkeypatch)
    with open(zrob_bombe(tmp_path / "b.xlsx"), "rb") as f:
        import_dyscyplin.plik.save("b.xlsx", f)
    import_dyscyplin.stworz_kolumny()
    assert import_dyscyplin.bledny
    assert "dekompresji" in import_dyscyplin.info
    assert import_dyscyplin.stan == import_dyscyplin.STAN.BLEDNY


def test_stworz_kolumny_za_duzy_czytelny_blad(
    import_dyscyplin, test1_xlsx, monkeypatch
):
    maly_limit_pliku(monkeypatch)
    with open(test1_xlsx, "rb") as f:
        import_dyscyplin.plik.save("test.xlsx", f)
    import_dyscyplin.stworz_kolumny()
    assert import_dyscyplin.bledny
    assert "limit" in import_dyscyplin.info
