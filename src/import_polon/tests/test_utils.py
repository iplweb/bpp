from pathlib import Path

import pytest

from import_polon.utils import (
    read_excel_or_csv_dataframe_guess_encoding,
    skroc_nazwe_pliku,
)

# Realna nazwa eksportu z POLON-u — 84 znaki, część odróżniająca (data) na końcu.
NAZWA_POLON = (
    "rozszerzone_zestawienie_pracownikow_podmiotu_"
    "na_dzien_wygenerowania_raportu_2026-01-15.xlsx"
)


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


def test_skroc_nazwe_pliku_krotka_bez_zmian():
    assert skroc_nazwe_pliku("krotka.xlsx") == "krotka.xlsx"


def test_skroc_nazwe_pliku_na_granicy_limitu():
    """Nazwa dokładnie długości limitu NIE jest skracana (brak wielokropka)."""
    nazwa = "a" * 32 + ".xls"  # dokładnie 36 znaków
    assert len(nazwa) == 36
    assert skroc_nazwe_pliku(nazwa, limit=36) == nazwa


def test_skroc_nazwe_pliku_gubi_katalog():
    """Prefiks z ``upload_to`` to szczegół implementacyjny — nie pokazujemy go."""
    assert skroc_nazwe_pliku("protected/import_polon/krotka.xlsx") == "krotka.xlsx"


def test_skroc_nazwe_pliku_dluga_miesci_sie_w_limicie():
    wynik = skroc_nazwe_pliku(NAZWA_POLON, limit=36)
    assert len(wynik) <= 36
    assert "…" in wynik


def test_skroc_nazwe_pliku_dluga_zachowuje_ogon_z_data():
    """Ogon niesie datę i rozszerzenie — jedyne, co odróżnia kolejne raporty."""
    wynik = skroc_nazwe_pliku(NAZWA_POLON, limit=36)
    assert wynik.endswith("2026-01-15.xlsx")
    assert wynik.startswith("rozszerzone")


def test_skroc_nazwe_pliku_dluga_ze_sciezka():
    wynik = skroc_nazwe_pliku(f"protected/import_polon/{NAZWA_POLON}", limit=36)
    assert wynik.endswith("2026-01-15.xlsx")
    assert "protected" not in wynik


def test_skroc_nazwe_pliku_pusta():
    """``plik`` niewypełniony (FileField bez pliku) → pusty napis, nie wyjątek."""
    assert skroc_nazwe_pliku("") == ""
    assert skroc_nazwe_pliku(None) == ""
