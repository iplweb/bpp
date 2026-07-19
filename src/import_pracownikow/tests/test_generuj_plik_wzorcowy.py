import os

import pytest
from django.core.management.base import CommandError

from import_pracownikow.management.commands.generuj_plik_wzorcowy import (
    NAGLOWKI,
    Command,
    zbuduj_workbook,
)


def test_naglowki_maja_15_kolumn_i_czyste_brzmienie():
    assert len(NAGLOWKI) == 15
    # Śmieci formatujące nie mogą wrócić:
    for h in NAGLOWKI:
        assert "\n" not in h
        assert h == h.strip()
    assert "Numer" in NAGLOWKI
    assert "Data końca zatrudnienia" in NAGLOWKI
    assert "Podstawowe miejsce pracy" in NAGLOWKI


def test_arkusz_pracownicy_naglowek_w_wierszu_1_z_pelna_ramka():
    wb = zbuduj_workbook()
    ws = wb["Pracownicy"]
    # Nagłówek w wierszu 1:
    wartosci = [ws.cell(row=1, column=c).value for c in range(1, 16)]
    assert wartosci == NAGLOWKI
    # Pełna ramka LRTB na KAŻDEJ komórce nagłówka:
    for c in range(1, 16):
        b = ws.cell(row=1, column=c).border
        assert all(s.style for s in (b.left, b.right, b.top, b.bottom)), (
            f"kolumna {c} nie ma pełnej ramki"
        )
        assert ws.cell(row=1, column=c).font.bold


def test_ma_4_wiersze_przykladowe():
    wb = zbuduj_workbook()
    ws = wb["Pracownicy"]
    # Wiersze 2..5 = dane; kolumna Nazwisko (2) niepusta w każdym:
    for r in range(2, 6):
        assert ws.cell(row=r, column=2).value not in (None, "")


def test_zakladka_opis_kolumn_nie_wpada_w_detekcje_naglowka():
    # Wierny odpowiednik runtime'owej fuzzy-detekcji: normalizujemy KAŻDĄ
    # komórkę i liczymy trafienia w TRY_NAMES. Żaden wiersz nie może mieć
    # ≥ MIN_POINTS trafień — inaczej find_similar_row wziąłby go za nagłówek
    # i „Opis kolumn" policzyłaby się jako drugi arkusz danych.
    from import_common.util import normalize_cell_header
    from import_pracownikow.mapping import MIN_POINTS, TRY_NAMES

    wb = zbuduj_workbook()
    assert "Opis kolumn" in wb.sheetnames
    ws = wb["Opis kolumn"]
    zbior = set(TRY_NAMES)
    for row in ws.iter_rows(values_only=True):
        trafienia = sum(
            1 for v in row if v is not None and normalize_cell_header(v) in zbior
        )
        assert trafienia < MIN_POINTS, f"wiersz wygląda jak nagłówek: {row}"


def test_komenda_odmawia_zapisu_przez_symlink(tmp_path):
    # Zapis przez dowiązanie symboliczne podążyłby za nim i nadpisał cel
    # (np. fixture testowy na starym checkoutcie) — komenda musi odmówić.
    cel = tmp_path / "cel.xlsx"
    cel.write_text("nietkniete")
    link = tmp_path / "link.xlsx"
    os.symlink(cel, link)

    with pytest.raises(CommandError):
        Command().handle(output=str(link))

    assert os.path.islink(link)  # symlink nietknięty
    assert cel.read_text() == "nietkniete"  # cel nie nadpisany
