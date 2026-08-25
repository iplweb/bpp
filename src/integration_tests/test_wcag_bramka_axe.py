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

from bpp.models import Autor, Uczelnia
from integration_tests import axe_helper
from powiazania_autorow.models import AuthorConnection

# Bramka NIE MOZE korzystac z automatycznego rerunu, ktory fixture `page`
# dokłada testom przegladarkowym. Naruszenie dostepnosci nie znika przy
# drugim podejsciu — jesli raz zapalilo, to jest realne. Rerun zamienilby
# je w migotanie i przepuscil.
pytestmark = pytest.mark.flaky(reruns=0)


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


def _sprawdz_strone(page, url, sentinel, nazwa):
    """Otwiera stronę, sprawdza że to właściwa strona, skanuje, asertuje zero.

    Sentinel jest po to, żeby zielona bramka nie mogła znaczyć „trafiliśmy
    na 404". Wspólny `base.html` dziedziczy nawet strona błędu, więc sama
    obecność jakichkolwiek elementów niczego nie dowodzi.
    """
    odpowiedz = page.goto(url, wait_until="networkidle")

    assert odpowiedz is not None and odpowiedz.status == 200, (
        f"{nazwa}: status {odpowiedz.status if odpowiedz else '?'}, "
        "bramka mierzyłaby nie tę stronę"
    )
    assert page.locator(sentinel).count() > 0, (
        f"{nazwa}: brak sentinela {sentinel} — to nie jest ta strona"
    )

    wynik = axe_helper.skanuj(page)

    print(f"\n[{nazwa}] {axe_helper.opisz_niejednoznaczne(wynik)}")

    assert wynik["violations"] == [], (
        f"{nazwa}: axe znalazł naruszenia WCAG 2.2 AA"
        + axe_helper.opisz_naruszenia(wynik)
    )


@pytest.mark.django_db(transaction=True)
def test_bramka_strona_autora(channels_live_server, page: Page, transactional_db):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    _sprawdz_strone(
        page,
        f"{channels_live_server.url}{reverse('bpp:browse_autor', args=[autor.slug])}",
        ".autor-page__title-input",
        "strona autora",
    )


@pytest.mark.django_db(transaction=True)
def test_bramka_strona_uczelni(channels_live_server, page: Page, transactional_db):
    uczelnia = baker.make(Uczelnia, nazwa="Uczelnia Testowa", skrot="UT")
    _sprawdz_strone(
        page,
        f"{channels_live_server.url}"
        f"{reverse('bpp:browse_uczelnia', args=[uczelnia.slug])}",
        ".uczelnia__tile-description",
        "strona uczelni",
    )


@pytest.mark.django_db(transaction=True)
def test_bramka_graf_powiazan(channels_live_server, page: Page, transactional_db):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    wsp = baker.make(Autor, imiona="Anna", nazwisko="Nowak", pokazuj=True)
    baker.make(
        AuthorConnection,
        primary_author=autor,
        secondary_author=wsp,
        shared_publications_count=3,
    )
    _sprawdz_strone(
        page,
        f"{channels_live_server.url}"
        f"{reverse('bpp:browse_autor_powiazania', args=[autor.pk])}",
        "#graf-nawigacja",
        "graf powiązań",
    )
