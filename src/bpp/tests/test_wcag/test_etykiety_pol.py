"""WCAG 1.3.1/4.1.2 — pola formularzy mają dostępne nazwy.

axe zgłosił `label` (critical) dla widocznego pola „Tytuł raportu" na
stronie autora. To samo pole jest w kolejnych szablonach, których bramka
axe nie obejmuje — stąd te testy.

Sprawdzamy POWIĄZANIE na wyrenderowanym DOM-ie (`lxml.html`), nie regexem
po źródle HTML: `<label for="zle-id">` istnieje i nie wiąże niczego, a
`aria-label` na ukrytym polu byłby bezużyteczny. Ten sam wzorzec parsowania
(`lxml.html.fromstring(...).xpath(...)`) stosuje sąsiedni
`test_alt_obrazy.py`.
"""

import lxml.html
import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.template.loader import render_to_string
from django.test import RequestFactory


def _widoczne_pola(drzewo):
    """Elementy `<input name="suggested-title">`, które NIE są ukryte."""
    return [
        pole
        for pole in drzewo.xpath('//input[@name="suggested-title"]')
        if (pole.get("type") or "").lower() != "hidden"
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
    drzewo = lxml.html.fromstring(html)

    pola = _widoczne_pola(drzewo)
    assert pola, f"{szablon}: nie znaleziono widocznego pola suggested-title"

    for pole in pola:
        # Pusty `aria-label=""` USUWA dostępną nazwę (WCAG 4.1.2), a nie ją
        # nadaje — `.strip()` odrzuca pusty string i sam biały znak jako
        # brak nazwy, tak samo jak dla `id=""`.
        aria_label = (pole.get("aria-label") or "").strip()
        ma_aria = bool(aria_label)

        identyfikator = (pole.get("id") or "").strip()
        ma_id = bool(identyfikator)

        assert ma_aria or ma_id, (
            f"{szablon}: pole bez dostępnej nazwy — "
            f"{lxml.html.tostring(pole, encoding='unicode')}"
        )
        if ma_id and not ma_aria:
            etykiety = drzewo.xpath(f'//label[@for="{identyfikator}"]')
            assert etykiety, (
                f"{szablon}: jest id={identyfikator}, ale żaden <label> "
                "go nie wskazuje — etykieta nie wiąże się z polem"
            )

            # Zduplikowany `id` rozrywa powiązanie label↔input: przeglądarka
            # (i czytnik ekranu) wiąże `<label for>` z PIERWSZYM elementem
            # o tym `id` w dokumencie. Jeśli to nie jest nasze pole, etykieta
            # jest bezużyteczna mimo formalnej obecności `for=`.
            z_tym_id = drzewo.xpath(f'//*[@id="{identyfikator}"]')
            assert len(z_tym_id) == 1, (
                f"{szablon}: id={identyfikator} występuje "
                f"{len(z_tym_id)}x w dokumencie — powiązanie label↔input "
                "jest niejednoznaczne"
            )
