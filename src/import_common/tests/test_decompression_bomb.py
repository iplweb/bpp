"""M9 (audyt bezpieczeństwa 2026-07): guard przed bombami dekompresyjnymi
(zip-bomb) w plikach XLSX ładowanych przez importery.

XLSX to archiwum ZIP — złośliwy plik ~KB może rozpakować się do GB i zabić
workera importu (OOM). Guard odrzuca taki plik PRZED załadowaniem do pamięci.
"""

import zipfile

import openpyxl
import pytest

from import_common.exceptions import DecompressionBombException
from import_common.util import (
    MAX_ROZMIAR_PO_DEKOMPRESJI,
    sprawdz_bombe_dekompresji,
)


def _zip_z_wpisem(path, rozmiar_rozpakowany):
    """XLSX-podobny ZIP z jednym silnie kompresowalnym wpisem (same zera)."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/worksheets/sheet1.xml", b"\0" * rozmiar_rozpakowany)


def test_guard_odrzuca_bombe_dekompresji(tmp_path):
    p = tmp_path / "bomba.xlsx"
    _zip_z_wpisem(str(p), 4 * 1024 * 1024)  # 4 MB po rozpakowaniu
    with pytest.raises(DecompressionBombException):
        sprawdz_bombe_dekompresji(str(p), max_rozpakowany=1024 * 1024)  # limit 1 MB


def test_guard_przepuszcza_normalny_xlsx(tmp_path):
    p = tmp_path / "ok.xlsx"
    wb = openpyxl.Workbook()
    wb.active["A1"] = "test"
    wb.save(str(p))
    # Domyślny limit (setki MB) — realny plik przechodzi bez wyjątku.
    sprawdz_bombe_dekompresji(str(p))
    assert MAX_ROZMIAR_PO_DEKOMPRESJI > 100 * 1024 * 1024


def test_guard_ignoruje_pliki_nie_zip(tmp_path):
    # .csv / stary .xls nie są archiwami ZIP → nie ten wektor, cicho przepuść.
    p = tmp_path / "dane.csv"
    p.write_text("a,b,c\n1,2,3\n")
    sprawdz_bombe_dekompresji(str(p))
