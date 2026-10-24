"""Bezpieczniki rozmiaru pliku importu list ministerialnych."""

import io

import openpyxl
import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from import_common.exceptions import DecompressionBombException, PlikZaDuzyException
from import_common.tests._pliki_limity import (
    maly_limit_dekompresji,
    maly_limit_pliku,
    zrob_bombe,
)
from import_list_ministerialnych.core import (
    analyze_excel_file_import_list_ministerialnych,
)
from import_list_ministerialnych.models import ImportListMinisterialnych
from import_list_ministerialnych.util import wczytaj_plik_importu_dyscyplin_zrodel


def _poprawny_xlsx(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Lp.", "Tytuł 1", "Punkty"])
    ws.append(["Lp.", "Tytuł 1", "Punkty"])
    ws.append([1, "Czasopismo", 100])
    buf = io.BytesIO()
    wb.save(buf)
    path.write_bytes(buf.getvalue())
    return str(path)


def test_wczytaj_odrzuca_bombe(tmp_path, monkeypatch):
    maly_limit_dekompresji(monkeypatch)
    with pytest.raises(DecompressionBombException):
        wczytaj_plik_importu_dyscyplin_zrodel(zrob_bombe(tmp_path / "b.xlsx"))


def test_wczytaj_odrzuca_za_duzy(tmp_path, monkeypatch):
    maly_limit_pliku(monkeypatch)
    with pytest.raises(PlikZaDuzyException):
        wczytaj_plik_importu_dyscyplin_zrodel(_poprawny_xlsx(tmp_path / "x.xlsx"))


def test_wczytaj_poprawny_plik(tmp_path):
    dane = wczytaj_plik_importu_dyscyplin_zrodel(_poprawny_xlsx(tmp_path / "x.xlsx"))
    assert dane == [{"Lp.": 1, "Tytuł 1": "Czasopismo", "Punkty": 100}]


@pytest.mark.django_db
def test_analyze_zapisuje_czytelny_blad_dla_bomby(tmp_path, monkeypatch):
    maly_limit_dekompresji(monkeypatch)
    parent = baker.make(ImportListMinisterialnych, rok=2023)
    with pytest.raises(DecompressionBombException):
        analyze_excel_file_import_list_ministerialnych(
            zrob_bombe(tmp_path / "b.xlsx"), parent, MockProgress(parent)
        )
    wiersz = parent.wierszimportulistyministerialnej_set.get()
    assert "dekompresji" in wiersz.rezultat
