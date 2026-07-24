"""#5 (security review): guard przed „grubym" plikiem importu.

Bomb-check pilnuje rozmiaru PO dekompresji, ale formalnie legalny, wielki plik
(setki MB), który po dekompresji mieści się pod progiem, i tak wciągnąłby cały
skoroszyt do RAM. Guard odrzuca taki plik PRZED przetwarzaniem.
"""

import openpyxl
import pytest

from import_common.exceptions import PlikZaDuzyException
from import_common.util import MAX_ROZMIAR_PLIKU, sprawdz_rozmiar_pliku


def test_guard_odrzuca_zbyt_duzy_plik(tmp_path):
    p = tmp_path / "gruby.xlsx"
    p.write_bytes(b"\0" * (2 * 1024 * 1024))  # 2 MB
    with pytest.raises(PlikZaDuzyException):
        sprawdz_rozmiar_pliku(str(p), max_bajtow=1024 * 1024)  # limit 1 MB


def test_guard_przepuszcza_normalny_plik(tmp_path):
    p = tmp_path / "ok.xlsx"
    wb = openpyxl.Workbook()
    wb.active["A1"] = "test"
    wb.save(str(p))
    # Domyślny limit (dziesiątki MB) — realny plik przechodzi bez wyjątku.
    sprawdz_rozmiar_pliku(str(p))
    assert MAX_ROZMIAR_PLIKU >= 50 * 1024 * 1024


def test_guard_ignoruje_brak_pliku(tmp_path):
    # Nieistniejąca ścieżka — nie ten wektor; niech padnie dalej (open()).
    sprawdz_rozmiar_pliku(str(tmp_path / "nie_ma.xlsx"))
