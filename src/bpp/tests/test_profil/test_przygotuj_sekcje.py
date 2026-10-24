"""Testy ``przygotuj_sekcje`` — widoczne sekcje z danymi, w kolejności.

Sekcje tylko-szablonowe są zawsze dołączane (partial sam się bramkuje, pusty
wynik odrzuca dopiero tag ``pasy_profilu``), sekcje data-driven — pomijane
gdy builder zwróci ``None`` (pusto).
"""

import pytest
from model_bakery import baker

from bpp.models import Autor
from bpp.profil_autora import (
    KLUCZ_AFILIACJA,
    KLUCZ_STATYSTYKI_CHARAKTER,
    KLUCZ_WYKRESY,
    SZEROKOSC_POL,
)
from bpp.profil_autora_dane import przygotuj_sekcje

pytestmark = pytest.mark.django_db


def _klucze(lista):
    return [s["klucz"] for s in lista]


def test_zwraca_plaska_liste_z_szerokoscia_i_karta():
    autor = baker.make(Autor)
    sekcje = przygotuj_sekcje(autor, uczelnia=None, request=None)
    assert isinstance(sekcje, list)
    for s in sekcje:
        assert {"klucz", "nazwa", "template", "dane", "szerokosc", "karta"} <= set(s)


def test_template_only_obecna_bez_buildera():
    # afiliacja to sekcja tylko-szablonowa (brak buildera danych) —
    # MUSI być obecna mimo braku danych (partial sam się bramkuje).
    autor = baker.make(Autor)
    sekcje = przygotuj_sekcje(autor, uczelnia=None, request=None)
    pozycja = next(s for s in sekcje if s["klucz"] == KLUCZ_AFILIACJA)
    assert pozycja["dane"] is None
    assert pozycja["template"].endswith("afiliacja.html")
    assert pozycja["szerokosc"] == SZEROKOSC_POL


def test_data_section_z_pustymi_danymi_jest_pomijana():
    # autor bez prac → statystyki i wykresy (buildery) zwracają None → pomijane
    autor = baker.make(Autor)
    klucze = _klucze(przygotuj_sekcje(autor, uczelnia=None, request=None))
    assert KLUCZ_STATYSTYKI_CHARAKTER not in klucze
    assert KLUCZ_WYKRESY not in klucze
