"""Sekcja „Podsumowanie dorobku": liczba publikacji, łączny IF i PK."""

from decimal import Decimal

import pytest
from django.template.loader import render_to_string
from django.utils import translation

from bpp.profil_autora import (
    KLUCZ_PODSUMOWANIE,
    KLUCZ_STATYSTYKI_CHARAKTER,
    rozwiaz_uklad,
)
from bpp.profil_autora_dane import _podsumowanie


@pytest.fixture
def dorobek(
    autor_jan_nowak,
    autor_jan_kowalski,
    jednostka,
    wydawnictwo_ciagle,
    wydawnictwo_zwarte,
):
    wydawnictwo_ciagle.impact_factor = Decimal("2.5")
    wydawnictwo_ciagle.punkty_kbn = Decimal("100")
    wydawnictwo_ciagle.rok = 2020
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)
    # Współautor nie może dublować pracy w sumach autora.
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)

    wydawnictwo_zwarte.impact_factor = Decimal("0")
    wydawnictwo_zwarte.punkty_kbn = Decimal("20")
    wydawnictwo_zwarte.rok = 2023
    wydawnictwo_zwarte.save()
    wydawnictwo_zwarte.dodaj_autora(autor_jan_nowak, jednostka)
    return autor_jan_nowak


@pytest.mark.django_db
def test_podsumowanie_sumuje_prace_autora(dorobek):
    dane = _podsumowanie(dorobek, None, None)
    assert dane["liczba"] == 2
    assert dane["impact_factor"] == Decimal("2.5")
    assert dane["punkty_kbn"] == Decimal("120")
    assert dane["rok_od"] == 2020
    assert dane["rok_do"] == 2023


@pytest.mark.django_db
def test_podsumowanie_liczy_tylko_prace_autora(dorobek, autor_jan_kowalski):
    dane = _podsumowanie(autor_jan_kowalski, None, None)
    assert dane["liczba"] == 1
    assert dane["punkty_kbn"] == Decimal("100")


@pytest.mark.django_db
def test_podsumowanie_bez_prac_ukrywa_sekcje(autor_jan_nowak):
    assert _podsumowanie(autor_jan_nowak, None, None) is None


def test_podsumowanie_domyslnie_pierwsze_na_stronie():
    klucze = [s["klucz"] for s in rozwiaz_uklad(None)]
    assert klucze[0] == KLUCZ_PODSUMOWANIE


def test_nowa_sekcja_wstawiana_na_swoje_miejsce_w_zapisanym_ukladzie():
    # Uczelnia z układem zapisanym przed dodaniem podsumowania: sekcja nie
    # ląduje na końcu strony, tylko na swoim miejscu z katalogu.
    class Uczelnia:
        uklad_profilu_autora = [{"klucz": KLUCZ_STATYSTYKI_CHARAKTER}]

    klucze = [s["klucz"] for s in rozwiaz_uklad(Uczelnia())]
    assert klucze.index(KLUCZ_PODSUMOWANIE) < klucze.index(KLUCZ_STATYSTYKI_CHARAKTER)


def test_szablon_podsumowania():
    with translation.override("pl"):
        html = _render_podsumowania()
    assert "12" in html
    assert "31,456" in html
    assert "840" in html
    assert "2010" in html and "2024" in html


def _render_podsumowania():
    return render_to_string(
        "browse/autor_sekcje/podsumowanie.html",
        {
            "nazwa": "Podsumowanie dorobku w bazie danych",
            "dane": {
                "liczba": 12,
                "impact_factor": Decimal("31.456"),
                "punkty_kbn": Decimal("840"),
                "rok_od": 2010,
                "rok_do": 2024,
            },
        },
    )


@pytest.mark.django_db
def test_strona_autora_pokazuje_podsumowanie(client, dorobek):
    tresc = client.get(dorobek.get_absolute_url()).content.decode()
    assert "Podsumowanie dorobku w bazie danych" in tresc
    assert "autor-page__podsumowanie" in tresc
