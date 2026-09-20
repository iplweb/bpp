"""WCAG 2.1.4 — mechanizm wyłączania skrótu `/`.

Skrót obsługiwany był w trzech publicznych miejscach naraz; dwa z nich
(`base.html` i `global_search_modal.html`) otwierały wyszukiwarkę
niezależnie, więc na jedno naciśnięcie `openGlobalSearch` wołane było
dwukrotnie. Duplikat zlikwidowano — zostaje handler w modalu.

Testy pilnują trzech rzeczy: modułu preferencji faktycznie podpiętego,
przełącznika w stopce oraz braku powrotu usuniętego handlera.
"""

import re
from pathlib import Path

import pytest
from django.template.loader import render_to_string

import bpp

SZABLONY = Path(__file__).resolve().parents[3] / "django_bpp" / "templates"

# Kotwiczymy na katalogu pakietu, nie na `parents[n]` od `__file__` — ścieżka
# liczona skokami w górę łamie się przy przeniesieniu pliku testowego.
UCZELNIA = (
    Path(bpp.__file__).resolve().parent / "templates" / "browse" / "uczelnia.html"
)


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


# --- guardy w `browse/uczelnia.html` ---------------------------------------
#
# Strona uczelni ma WŁASNY, inline'owy skrypt (baner reklamujący skrót `/`
# plus handler zamykający ten baner) — niezależny od `base.html` i modalu.
# Oba miejsca musiały dostać ten sam warunek preferencji, bo inaczej strona
# główna reklamowałaby i obsługiwała skrót, który użytkownik wyłączył.
# Bez tych asercji usunięcie któregokolwiek guardu przechodzi CI: żaden test
# Pythona nie renderuje tej strony, a Playwright jej nie odwiedza.


def _skrypt_uczelni():
    return UCZELNIA.read_text(encoding="utf-8")


def test_uczelnia_baner_nie_reklamuje_wylaczonego_skrotu():
    tresc = _skrypt_uczelni()
    # Warunek pokazania banera musi być bramkowany preferencją — sam
    # `bannerDismissed` nie wystarczy.
    warunek = re.search(r"if\s*\(\s*skrotyWl\s*\n?\s*&&\s*\(!bannerDismissed", tresc)
    assert warunek, (
        "baner skrótu pokazuje się bez sprawdzenia preferencji — "
        "reklamowalibyśmy skrót, który użytkownik wyłączył (2.1.4)"
    )


def test_uczelnia_handler_zamykajacy_pyta_o_preferencje():
    tresc = _skrypt_uczelni()
    handler = re.search(r"if\s*\(e\.key === '/'[^)]*\)", tresc)
    assert handler, "zniknął handler `/` na stronie uczelni"
    assert "skrotyWl" in handler.group(0), (
        "handler `/` na stronie uczelni reaguje mimo wyłączonego skrótu"
    )


def test_uczelnia_oba_guardy_maja_typeof():
    # Gdy moduł się nie załaduje, gołe wywołanie rzuciłoby TypeError i zabiło
    # cały inline'owy skrypt strony głównej — nie tylko sam skrót.
    assert _skrypt_uczelni().count("typeof window.bppSkrotyWlaczone") == 2, (
        "oba guardy na stronie uczelni muszą tolerować brak modułu"
    )


@pytest.mark.django_db
def test_stopka_ma_przelacznik(client):
    html = render_to_string("base_footer.html", {})

    assert 'id="bpp-przelacznik-skrotow"' in html
    assert "aria-pressed" in html
    assert 'type="button"' in html
