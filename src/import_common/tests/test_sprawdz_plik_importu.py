"""Wspólny bezpiecznik plików importu: limit rozmiaru + bomba dekompresji,
dla ścieżek i obiektów plikowych Django."""

import io
from pathlib import Path

import openpyxl
import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from import_common.exceptions import (
    DecompressionBombException,
    NiebezpiecznyPlikException,
    PlikZaDuzyException,
)
from import_common.sources import otworz_zrodlo
from import_common.tests._pliki_limity import (
    MALY_LIMIT_PLIKU,
    maly_limit_dekompresji,
    maly_limit_pliku,
    zrob_bombe,
    zrob_duzy_plik,
)
from import_common.util import sprawdz_plik_importu


def _xlsx_bytes():
    wb = openpyxl.Workbook()
    wb.active["A1"] = "nazwisko"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_wyjatki_maja_wspolna_baze():
    assert issubclass(PlikZaDuzyException, NiebezpiecznyPlikException)
    assert issubclass(DecompressionBombException, NiebezpiecznyPlikException)


def test_za_duzy_plik(tmp_path, monkeypatch):
    maly_limit_pliku(monkeypatch)
    with pytest.raises(PlikZaDuzyException):
        sprawdz_plik_importu(zrob_duzy_plik(tmp_path / "duzy.csv"))


def test_bomba(tmp_path, monkeypatch):
    maly_limit_dekompresji(monkeypatch)
    with pytest.raises(DecompressionBombException):
        sprawdz_plik_importu(zrob_bombe(tmp_path / "b.xlsx"))


def test_poprawny_plik_przechodzi(tmp_path):
    p = tmp_path / "ok.xlsx"
    p.write_bytes(_xlsx_bytes())
    sprawdz_plik_importu(str(p))
    sprawdz_plik_importu(p)  # pathlib.Path też


def test_jawne_limity_maja_pierwszenstwo(tmp_path):
    p = tmp_path / "ok.xlsx"
    p.write_bytes(_xlsx_bytes())
    with pytest.raises(PlikZaDuzyException):
        sprawdz_plik_importu(str(p), max_bajtow=10)


def test_obiekt_plikowy_za_duzy(monkeypatch):
    maly_limit_pliku(monkeypatch)
    f = SimpleUploadedFile("x.xlsx", b"\0" * (MALY_LIMIT_PLIKU + 1))
    with pytest.raises(PlikZaDuzyException):
        sprawdz_plik_importu(f)


def test_obiekt_plikowy_bomba(tmp_path, monkeypatch):
    maly_limit_dekompresji(monkeypatch)
    dane = Path(zrob_bombe(tmp_path / "b.xlsx")).read_bytes()
    with pytest.raises(DecompressionBombException):
        sprawdz_plik_importu(SimpleUploadedFile("b.xlsx", dane))


def test_obiekt_plikowy_ok_przywraca_pozycje():
    f = SimpleUploadedFile("ok.xlsx", _xlsx_bytes())
    f.seek(0)
    sprawdz_plik_importu(f)
    assert f.tell() == 0
    openpyxl.load_workbook(f)  # nadal czytelny po sprawdzeniu


def test_otworz_zrodlo_csv_za_duzy(tmp_path, monkeypatch):
    maly_limit_pliku(monkeypatch)
    with pytest.raises(PlikZaDuzyException):
        otworz_zrodlo(zrob_duzy_plik(tmp_path / "duzy.csv"))


def test_otworz_zrodlo_csv_ok(tmp_path):
    p = tmp_path / "ok.csv"
    p.write_bytes(b"Nazwisko;Imie;Jedn org\nKowalski;Jan;Katedra\n")
    assert otworz_zrodlo(str(p), min_points=2).count() == 1


def test_ewaluacja2021_validate_xlsx_bomba(tmp_path, monkeypatch):
    from ewaluacja2021.validators import validate_xlsx

    maly_limit_dekompresji(monkeypatch)
    dane = Path(zrob_bombe(tmp_path / "b.xlsx")).read_bytes()
    with pytest.raises(ValidationError, match="dekompresji"):
        validate_xlsx(SimpleUploadedFile("b.xlsx", dane))


def test_ewaluacja2021_validate_xlsx_za_duzy(monkeypatch):
    from ewaluacja2021.validators import validate_xlsx

    maly_limit_pliku(monkeypatch)
    with pytest.raises(ValidationError, match="limit"):
        validate_xlsx(SimpleUploadedFile("x.xlsx", _xlsx_bytes()))


def test_ewaluacja2021_validate_xlsx_ok():
    from ewaluacja2021.validators import validate_xlsx

    wb = validate_xlsx(SimpleUploadedFile("ok.xlsx", _xlsx_bytes()))
    assert wb.active["A1"].value == "nazwisko"
