"""Testy renderu współdzielonego partiala listy prac (klik w całą pozycję)."""

from types import SimpleNamespace

import pytest
from django.template.loader import render_to_string

pytestmark = pytest.mark.django_db


def _praca(url="/bpp/rekord/wydawnictwo_zwarte/1/", opis="Opis bibliograficzny"):
    return SimpleNamespace(
        get_absolute_url=lambda: url,
        opis_bibliograficzny_cache=opis,
    )


def test_cala_pozycja_klikalna_przez_nakladke():
    html = render_to_string(
        "browse/autor_sekcje/_lista_prac.html",
        {"nazwa": "Najlepsze prace", "dane": {"prace": [_praca()]}},
    )
    assert "autor-page__praca-overlay" in html
    assert 'href="/bpp/rekord/wydawnictwo_zwarte/1/"' in html


def test_brak_linku_szczegoly():
    html = render_to_string(
        "browse/autor_sekcje/_lista_prac.html",
        {"nazwa": "Najlepsze prace", "dane": {"prace": [_praca()]}},
    )
    assert "[szczegóły]" not in html


def test_opis_renderowany_w_kontenerze_z_line_clamp():
    html = render_to_string(
        "browse/autor_sekcje/_lista_prac.html",
        {"nazwa": "Najlepsze prace", "dane": {"prace": [_praca(opis="Tytuł pracy")]}},
    )
    assert "Tytuł pracy" in html
    assert "autor-page__praca-opis" in html
