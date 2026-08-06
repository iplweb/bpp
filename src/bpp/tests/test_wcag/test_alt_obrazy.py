"""WCAG 1.1.1 — treść nietekstowa.

Ikona obok pełnego komunikatu tekstowego jest DEKORACJĄ, więc właściwą
wartością jest ``alt=""`` (pusty), a nie opis. Pusty ``alt`` każe czytnikowi
element POMINĄĆ; brak atrybutu każe mu odczytać nazwę pliku
("database dot es vee gee").
"""

from pathlib import Path

import pytest
import lxml.html
from django.template.loader import render_to_string

SZABLONY = Path(__file__).resolve().parents[2] / "templates"


@pytest.mark.django_db
def test_504_ma_pusty_alt_na_ikonie():
    html = render_to_string("504.html")
    obrazy = lxml.html.fromstring(html).xpath("//img")

    assert obrazy, "szablon 504.html powinien zawierać <img>"
    for img in obrazy:
        assert img.get("alt") == "", (
            f"<img src={img.get('src')!r}> musi mieć alt='' (dekoracja)"
        )


@pytest.mark.django_db
def test_martwy_szablon_autocomplete_usuniety():
    # Szablon renderował <img> bez alt, ale nie był używany: widok
    # bpp:navigation-autocomplete zwraca JSON (Select2QuerySetSequenceView),
    # a listę rysuje Select2 po stronie klienta.
    assert not (SZABLONY / "user_navigation_autocomplete.html").exists()


@pytest.mark.django_db
def test_504_deklaruje_jezyk_polski():
    # WCAG 3.1.1 (Language of Page, poziom A). Treść strony jest polska
    # ("Przekroczono dozwolony czas wykonywania zapytania"), a dokument
    # deklarował lang="en" — czytnik odczytywał CAŁĄ stronę angielską
    # fonetyką. Jedyny samodzielny szablon z własnym <html lang=…>;
    # pozostałe dziedziczą po base.html.
    html = render_to_string("504.html")
    korzen = lxml.html.fromstring(html)

    assert korzen.get("lang") == "pl"
