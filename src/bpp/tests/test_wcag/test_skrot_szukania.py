"""WCAG 2.1.4 — mechanizm wyłączania skrótu `/`.

Skrót obsługiwany był w trzech publicznych miejscach naraz; dwa z nich
(`base.html` i `global_search_modal.html`) otwierały wyszukiwarkę
niezależnie, więc na jedno naciśnięcie `openGlobalSearch` wołane było
dwukrotnie. Duplikat zlikwidowano — zostaje handler w modalu.

Testy pilnują trzech rzeczy: modułu preferencji faktycznie podpiętego,
przełącznika w stopce oraz braku powrotu usuniętego handlera.
"""

from pathlib import Path

import pytest
from django.template.loader import render_to_string

SZABLONY = Path(__file__).resolve().parents[3] / "django_bpp" / "templates"


def _tresc(nazwa):
    return (SZABLONY / nazwa).read_text(encoding="utf-8")


def test_modul_skrotow_podpiety_w_base():
    # Bez tego tagu przełącznik i warunki w handlerach przestają działać,
    # a żaden inny test by tego nie wykrył.
    assert "skroty-klawiszowe.js" in _tresc("base.html")


def test_base_nie_ma_juz_wlasnego_handlera_skrotu():
    # Dowód likwidacji duplikatu: handler żyje wyłącznie w modalu.
    tresc = _tresc("base.html")
    assert "e.key === '/'" not in tresc


def test_modal_pyta_o_preferencje():
    tresc = _tresc("global_search_modal.html")
    assert "e.key === '/'" in tresc
    assert "bppSkrotyWlaczone" in tresc


def test_modal_ma_guard_typeof():
    # Gdy moduł się nie załaduje, gołe wywołanie rzucałoby TypeError przy
    # każdym naciśnięciu `/` i skrót umarłby po cichu.
    assert "typeof window.bppSkrotyWlaczone" in _tresc("global_search_modal.html")


@pytest.mark.django_db
def test_stopka_ma_przelacznik(client):
    html = render_to_string("base_footer.html", {})

    assert 'id="bpp-przelacznik-skrotow"' in html
    assert 'aria-pressed' in html
    assert 'type="button"' in html
