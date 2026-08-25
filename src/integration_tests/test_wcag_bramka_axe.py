"""Bramka dostępności: axe-core na publicznych stronach BPP (WCAG faza 3).

Próg to ZERO naruszeń, bez pliku baseline — przy czternastu naprawianych
naruszeniach zapadka byłaby droższa niż sama naprawa.

WYMAGANIE WSTĘPNE: `make assets`. Bez niego nie ma `axe.min.js` w statykach
ani zbudowanego CSS, więc pomiar kontrastu byłby bez sensu.
"""

import pytest
from django.urls import reverse
from model_bakery import baker
from playwright.sync_api import Page

from bpp.models import Autor
from integration_tests import axe_helper


@pytest.mark.django_db(transaction=True)
def test_axe_daje_sie_uruchomic(channels_live_server, page: Page, transactional_db):
    """Sanity dla samego harnessu: axe się wstrzykuje i coś ocenia.

    Osobny test od bramki, bo odpowiada na inne pytanie. Bramka mówi „brak
    naruszeń"; ten mówi „pomiar w ogóle się odbył". Bez niego zielona bramka
    mogłaby znaczyć, że axe się nie załadował.
    """
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    page.goto(
        f"{channels_live_server.url}{reverse('bpp:browse_autor', args=[autor.slug])}",
        wait_until="networkidle",
    )

    wynik = axe_helper.skanuj(page)

    ocenione = len(wynik["violations"]) + len(wynik["passes"])
    assert ocenione > 10, (
        f"axe ocenił tylko {ocenione} reguł — wygląda, jakby się nie "
        "uruchomił albo trafił na pustą stronę"
    )
