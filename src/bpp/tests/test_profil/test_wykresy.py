"""Testy wykresów rocznych: agregacja po latach + próg liniowy/słupkowy."""

from decimal import Decimal

import pytest
from django.template.loader import render_to_string

from bpp.profil_autora_dane import (
    OKNO_LAT_WYKRESU,
    _agreguj_po_latach,
    _ostatnie_lata,
    _wykres_if_lata,
    _wykres_pk_lata,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def autor_z_pracami(autor_jan_nowak, jednostka, wydawnictwo_ciagle, wydawnictwo_zwarte):
    def _ustaw(punkty_kbn, impact_factor):
        for rok, praca in ((2019, wydawnictwo_ciagle), (2020, wydawnictwo_zwarte)):
            praca.rok = rok
            praca.punkty_kbn = punkty_kbn
            praca.impact_factor = impact_factor
            praca.save()
            praca.dodaj_autora(autor_jan_nowak, jednostka)
        return autor_jan_nowak

    return _ustaw


@pytest.mark.parametrize("builder", [_wykres_pk_lata, _wykres_if_lata])
def test_wykres_ukryty_gdy_same_zera(autor_z_pracami, builder):
    autor = autor_z_pracami(Decimal("0"), Decimal("0"))
    assert builder(autor, None, None) is None


@pytest.mark.parametrize("builder", [_wykres_pk_lata, _wykres_if_lata])
def test_wykres_widoczny_gdy_niezerowe(autor_z_pracami, builder):
    autor = autor_z_pracami(Decimal("20"), Decimal("1.5"))
    dane = builder(autor, None, None)
    assert dane is not None
    assert [rok for rok, _w in dane["dane"]] == [2019, 2020]


def test_ostatnie_lata_ogranicza_do_okna():
    # 25 lat danych → wykres pokazuje tylko ostatnie OKNO_LAT_WYKRESU.
    dane = [(rok, 1) for rok in range(2000, 2025)]
    okno = _ostatnie_lata(dane)
    assert len(okno) == OKNO_LAT_WYKRESU
    assert okno[-1][0] == 2024
    assert okno[0][0] == 2024 - OKNO_LAT_WYKRESU + 1


def test_ostatnie_lata_krotsza_seria_bez_zmian():
    dane = [(2020, 1), (2021, 2), (2022, 3)]
    assert _ostatnie_lata(dane) == dane


def test_agreguj_sumuje_wartosci_w_obrebie_roku():
    dane, maks, suma = _agreguj_po_latach([(2020, 5), (2020, 3), (2021, 4)])
    assert dane == [(2020, 8), (2021, 4)]
    assert maks == 8
    assert suma == 12


def test_agreguj_pomija_none():
    dane, maks, suma = _agreguj_po_latach([(None, 5), (2021, None), (2021, 2)])
    assert dane == [(2021, 2)]
    assert maks == 2
    assert suma == 2


def test_agreguj_pusty():
    assert _agreguj_po_latach([]) == ([], 0, 0)


def _render(dane):
    maks = max((w for _r, w in dane), default=0)
    return render_to_string(
        "browse/autor_sekcje/_wykres_lata.html",
        {"nazwa": "Wykres", "dane": {"dane": dane, "maks": maks, "etykieta": "prac"}},
    )


def test_do_10_lat_slupkowy():
    dane = [(2010 + i, i + 1) for i in range(5)]
    html = _render(dane)
    assert "autor-page__slupek" in html
    assert "<polyline" not in html


def test_powyzej_10_lat_liniowy():
    dane = [(2000 + i, i + 1) for i in range(12)]
    html = _render(dane)
    assert "<polyline" in html
    assert "autor-page__slupek" not in html


def test_liniowy_ma_os_Y_z_maks_i_siatka():
    # Wariant liniowy (>10 lat): oś Y jako HTML (maks + 0) i siatka jako <line>.
    dane = [(2000 + i, i + 2) for i in range(12)]
    maks = max(w for _r, w in dane)
    html = _render(dane)
    assert "autor-page__wykres-osY" in html
    assert str(maks) in html
    assert "autor-page__wykres-siatka" in html
    # Pełna i połówkowa linia siatki w grupie transformowanej.
    assert html.count("<line") >= 2


def test_slupkowy_ma_os_Y_z_maks_i_siatka():
    # Wariant słupkowy (<=10 lat): etykieta maks (HTML) + górna linia siatki.
    dane = [(2010 + i, (i + 1) * 4) for i in range(5)]
    maks = max(w for _r, w in dane)
    html = _render(dane)
    assert "autor-page__wykres-osY" in html
    assert str(maks) in html
    assert "autor-page__wykres-siatka" in html
