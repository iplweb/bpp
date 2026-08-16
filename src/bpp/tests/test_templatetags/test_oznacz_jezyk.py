"""Filtr ``|oznacz_jezyk:`` — atrybut ``lang`` na tytule (WCAG 3.1.2).

Kryterium 3.1.2 wymaga oznaczenia fragmentu w innym języku niż język
strony. ``lang=""`` (pusty) jest GORSZY niż brak atrybutu: unieważnia
dziedziczenie z ``<html lang="pl">``, więc fragment, który bez atrybutu
zostałby odczytany poprawnie po polsku, staje się "językiem nieznanym".
Stąd wymóg, by przy braku danych atrybut nie pojawiał się wcale.
"""

import pytest
from django.template import Context, Template
from django.utils.safestring import SafeString, mark_safe

from bpp.templatetags.prace import oznacz_jezyk


class FakeJezyk:
    """Zastępnik ``Jezyk`` — filtr czyta wyłącznie ``kod_bcp47``."""

    def __init__(self, kod_bcp47):
        self.kod_bcp47 = kod_bcp47


def test_oznacz_jezyk_owija_gdy_kod_niepusty():
    assert oznacz_jezyk("Effects of X", FakeJezyk("en")) == (
        '<span lang="en">Effects of X</span>'
    )


def test_oznacz_jezyk_obsluguje_kod_regionalny():
    assert oznacz_jezyk("Colour", FakeJezyk("en-GB")) == (
        '<span lang="en-GB">Colour</span>'
    )


def test_oznacz_jezyk_pomija_atrybut_gdy_kod_pusty():
    wynik = oznacz_jezyk("Tytuł", FakeJezyk(""))
    assert wynik == "Tytuł"
    assert "lang=" not in wynik


def test_oznacz_jezyk_pomija_atrybut_gdy_brak_jezyka():
    wynik = oznacz_jezyk("Tytuł", None)
    assert wynik == "Tytuł"
    assert "<span" not in wynik


def test_oznacz_jezyk_pomija_atrybut_gdy_kod_to_none():
    assert oznacz_jezyk("Tytuł", FakeJezyk(None)) == "Tytuł"


def test_oznacz_jezyk_zachowuje_bezpieczny_html_wartosci():
    # Wartość po |safe_tytul jest SafeString z zamierzoną kursywą —
    # opakowanie nie może jej podwójnie zescape'ować.
    wartosc = mark_safe("Rola <i>Candida</i> w zakażeniach")
    assert oznacz_jezyk(wartosc, FakeJezyk("pl")) == (
        '<span lang="pl">Rola <i>Candida</i> w zakażeniach</span>'
    )


def test_oznacz_jezyk_escapuje_wartosc_niebezpieczna():
    # Gdyby filtr trafił na wartość NIE-safe (pominięty |safe_tytul),
    # nie wolno mu przepuścić surowego HTML-a.
    wynik = oznacz_jezyk("<script>alert(1)</script>", FakeJezyk("en"))
    assert "<script>" not in wynik
    assert "&lt;script&gt;" in wynik


def test_oznacz_jezyk_escapuje_kod_jezyka():
    # kod_bcp47 pochodzi ze słownika edytowalnego w adminie.
    wynik = oznacz_jezyk("Tytuł", FakeJezyk('en" onload="x'))
    assert 'onload="x"' not in wynik


def test_oznacz_jezyk_zwraca_safestring():
    assert isinstance(oznacz_jezyk("Tytuł", FakeJezyk("en")), SafeString)


@pytest.mark.parametrize(
    "kod,oczekiwany",
    [("en", '<span lang="en">Tytuł</span>'), ("", "Tytuł")],
)
def test_oznacz_jezyk_dziala_w_szablonie(kod, oczekiwany):
    tpl = Template("{% load prace %}{{ tytul|oznacz_jezyk:jezyk }}")
    wynik = tpl.render(Context({"tytul": "Tytuł", "jezyk": FakeJezyk(kod)}))
    assert wynik == oczekiwany
