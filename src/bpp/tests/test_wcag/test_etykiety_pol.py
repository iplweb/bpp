"""WCAG 1.3.1/4.1.2 — pola formularzy mają dostępne nazwy.

axe zgłosił `label` (critical) dla widocznego pola „Tytuł raportu" na
stronie autora. To samo pole jest w kolejnych szablonach, których bramka
axe nie obejmuje — stąd te testy.

Sprawdzamy POWIĄZANIE, nie obecność znacznika: `<label for="zle-id">`
istnieje i nie wiąże niczego, a `aria-label` na ukrytym polu byłby
bezużyteczny.
"""

import re

import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.template.loader import render_to_string
from django.test import RequestFactory

WZORZEC_POLA = re.compile(r'<input[^>]*name="suggested-title"[^>]*>', re.IGNORECASE)


def _widoczne_pola(html):
    """Pola `suggested-title`, które NIE są ukryte."""
    return [
        znacznik
        for znacznik in WZORZEC_POLA.findall(html)
        if 'type="hidden"' not in znacznik.lower()
    ]


def _html_request():
    """Minimalny ``HttpRequest`` z sesją i anonimowym użytkownikiem.

    ``jednostka.html``/``zrodlo.html`` dziedziczą po ``base.html`` →
    ``bare.html`` (pasek nawigacji, stopka), a te wymagają realnego
    ``request`` — m.in. ``{% czy_pokazywac %}`` czyta ``context.request``,
    a filtr ``{{ uczelnia.nazwa|default:uczelnia.skrot }}`` w ``bare.html``
    rzuca ``VariableDoesNotExist``, gdy kontekst nie przeszedł przez
    procesory kontekstu (``request=None`` w ``render_to_string`` renderuje
    zwykłym ``Context``, nie ``RequestContext``). Podanie ``request=``
    uruchamia procesory kontekstu — w tym ``bpp.context_processors.uczelnia``,
    które przez ``Uczelnia.objects.get_for_request`` odnajdą jedyną
    ``Uczelnia`` stworzoną pośrednio przez fixture ``jednostka``/``zrodlo``.
    """
    html_request = RequestFactory().get("/")
    html_request.user = AnonymousUser()
    html_request.session = SessionStore()
    return html_request


# `browse/autor.html` NIE jest tu parametryzowany — jego pole pilnuje
# bramka axe (Task 5) na realnie wyrenderowanej stronie, co jest mocniejsze
# niz render szablonu. `browse/tytul_raportu.html` byl martwym szablonem
# (zaden widok ani `{% include %}` go nie uzywal — sprawdzono literalnie i
# pod katem `{% include zmienna %}`) — Task 2 go usunal, wiec nie ma go na
# tej liscie.
@pytest.mark.parametrize(
    "szablon, nazwa_fixture",
    [
        ("browse/jednostka.html", "jednostka"),
        ("browse/zrodlo.html", "zrodlo"),
    ],
)
@pytest.mark.django_db
def test_widoczne_pole_tytulu_ma_dostepna_nazwe(szablon, nazwa_fixture, request):
    obiekt = request.getfixturevalue(nazwa_fixture)
    html = render_to_string(szablon, {nazwa_fixture: obiekt}, request=_html_request())

    pola = _widoczne_pola(html)
    assert pola, f"{szablon}: nie znaleziono widocznego pola suggested-title"

    for pole in pola:
        # Sprawdzamy WARTOŚĆ atrybutu, nie samą jego obecność: pusty
        # `aria-label=""` USUWA dostępną nazwę (WCAG 4.1.2), a nie ją
        # nadaje — substring-check `"aria-label=" in pole` przepuściłby
        # to jako poprawne. To samo dotyczy `id=""`: bez tej poprawki
        # `re.search(...).group(1)` na pustym dopasowaniu i tak by nie
        # wybuchł (grupa dopasowuje pusty string), ale dawałby
        # `identyfikator = ""` i mylące `for=""` w komunikacie zamiast
        # jasnego „pole bez dostępnej nazwy".
        aria_match = re.search(r'aria-label="([^"]*)"', pole, re.IGNORECASE)
        ma_aria = bool(aria_match and aria_match.group(1).strip())

        id_match = re.search(r'id="([^"]*)"', pole, re.IGNORECASE)
        ma_id = bool(id_match and id_match.group(1).strip())

        assert ma_aria or ma_id, f"{szablon}: pole bez dostępnej nazwy — {pole}"
        if ma_id and not ma_aria:
            identyfikator = id_match.group(1)
            assert f'for="{identyfikator}"' in html, (
                f"{szablon}: jest id={identyfikator}, ale żaden <label> "
                "go nie wskazuje — etykieta nie wiąże się z polem"
            )
