"""Testy ``przygotuj_sekcje`` — budowanie sekcji OBU kolumn z danymi.

Sekcje tylko-szablonowe (lewa kolumna) są zawsze dołączane (partial sam się
bramkuje), sekcje data-driven (prawa kolumna) — pomijane gdy builder zwróci
``None`` (pusto).
"""

import pytest
from model_bakery import baker

from bpp.models import Autor
from bpp.profil_autora import (
    KLUCZ_IDENTYFIKATORY,
    KLUCZ_STATYSTYKI_CHARAKTER,
    KOLUMNA_LEWA,
    KOLUMNA_PRAWA,
)
from bpp.profil_autora_dane import przygotuj_sekcje

pytestmark = pytest.mark.django_db


def _klucze(lista):
    return [s["klucz"] for s in lista]


def test_zwraca_obie_kolumny():
    autor = baker.make(Autor)
    sekcje = przygotuj_sekcje(autor, uczelnia=None, request=None)
    assert set(sekcje.keys()) == {KOLUMNA_LEWA, KOLUMNA_PRAWA}


def test_template_only_lewa_obecna_bez_buildera():
    # identyfikatory to sekcja tylko-szablonowa (brak buildera danych) —
    # MUSI być obecna mimo braku danych (partial sam się bramkuje).
    autor = baker.make(Autor)
    sekcje = przygotuj_sekcje(autor, uczelnia=None, request=None)
    lewa = _klucze(sekcje[KOLUMNA_LEWA])
    assert KLUCZ_IDENTYFIKATORY in lewa
    # sekcja template-only ma dane=None
    pozycja = next(
        s for s in sekcje[KOLUMNA_LEWA] if s["klucz"] == KLUCZ_IDENTYFIKATORY
    )
    assert pozycja["dane"] is None
    assert pozycja["template"].endswith("identyfikatory.html")


def test_data_section_z_pustymi_danymi_jest_pomijana():
    # autor bez prac → statystyki wg charakteru (builder) zwraca None → pomijane
    autor = baker.make(Autor)
    sekcje = przygotuj_sekcje(autor, uczelnia=None, request=None)
    assert KLUCZ_STATYSTYKI_CHARAKTER not in _klucze(sekcje[KOLUMNA_PRAWA])
