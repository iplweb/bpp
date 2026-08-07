"""WCAG 2.1.4 i 2.5.7/2.1.1 — testy zachowania w przeglądarce.

Testy szablonowe (``src/bpp/tests/test_wcag/``) dowodzą, że kod jest w
pliku; te dowodzą, że działa. Bez nich usunięcie warunku
``bppSkrotyWlaczone()`` z handlera skrótu ``/``, albo ``preventDefault``
z obsługi klawiatury grafu, albo samych handlerów kliknięcia przycisków
nawigacji — nie wywaliłoby żadnego testu.

Widok strony autora (``bpp:browse_autor``) wybrany zamiast strony uczelni,
bo nie wymaga obiektu ``Uczelnia`` w bazie (patrz też
``test_siec3d_bez_webgl.py``, który idzie tą samą drogą), a stopka i modal
wyszukiwarki renderują się na nim tak samo.

WYMAGANIE WSTĘPNE: ``make assets`` — bez zbudowanego bundla strona nie ma
czego wykonać i testy padną na braku elementów / błędnym zachowaniu JS.
"""

import pytest
from django.urls import reverse
from model_bakery import baker
from playwright.sync_api import Page, expect

from bpp.models import Autor


def _url_autora(channels_live_server):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    return (
        f"{channels_live_server.url}"
        f"{reverse('bpp:browse_autor', args=[autor.slug])}"
    )


def _url_grafu(channels_live_server):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    return (
        f"{channels_live_server.url}"
        f"{reverse('bpp:browse_autor_powiazania', args=[autor.pk])}"
    )


def _idz_na_strone(page: Page, url: str) -> None:
    """Nawiguje na `url`, obchodząc dwa źródła flakiness NIEZWIĄZANE z
    testowaną logiką (odkryte empirycznie przy pisaniu tego pliku):

    1. Baner RODO (``#CookielawBanner``, ``fixed``, wysoki z-index) renderuje
       się serwerowo, dopóki request nie niesie ciasteczka
       ``cookielaw_accepted`` (patrz ``cookielaw.templatetags`` w pakiecie
       ``cookielaw``) — bez tego ciasteczka przechwytuje kliknięcia na
       ``#bpp-przelacznik-skrotow`` i przyciskach nawigacji grafu, więc
       ustawiamy je PRZED nawigacją zamiast klikać "Zgadzam się" w każdym
       teście.
    2. Realne zdarzenia klawiatury (CDP ``Input.dispatchKeyEvent``) potrafią
       trafić w nieaktywną kartę, gdy w kontekście przeglądarki istnieje
       więcej niż jedna strona (współdzielony ``channels_live_server`` +
       fixture ``page`` w wielu testach) — bez ``bring_to_front()``
       ``document.activeElement`` po naciśnięciu klawisza gubi fokus
       ustawiony chwilę wcześniej przez ``locator.focus()``.
    """
    page.context.add_cookies(
        [{"name": "cookielaw_accepted", "value": "1", "url": url}]
    )
    page.goto(url, wait_until="domcontentloaded")
    page.bring_to_front()


# --- WCAG 2.1.4: skrót klawiszowy `/` i jego wyłącznik --------------------


@pytest.mark.django_db(transaction=True)
def test_skrot_otwiera_wyszukiwarke_domyslnie(
    channels_live_server, page: Page, transactional_db
):
    _idz_na_strone(page, _url_autora(channels_live_server))

    page.keyboard.press("/")

    expect(page.locator("#globalSearchModal")).to_be_visible(timeout=5000)


@pytest.mark.django_db(transaction=True)
def test_wylaczenie_skrotu_dziala(
    channels_live_server, page: Page, transactional_db
):
    _idz_na_strone(page, _url_autora(channels_live_server))

    page.locator("#bpp-przelacznik-skrotow").click()
    page.keyboard.press("/")
    page.wait_for_timeout(500)

    expect(page.locator("#globalSearchModal")).not_to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_ponowne_wlaczenie_przywraca_skrot(
    channels_live_server, page: Page, transactional_db
):
    _idz_na_strone(page, _url_autora(channels_live_server))

    przelacznik = page.locator("#bpp-przelacznik-skrotow")
    przelacznik.click()
    przelacznik.click()
    page.keyboard.press("/")

    expect(page.locator("#globalSearchModal")).to_be_visible(timeout=5000)


@pytest.mark.django_db(transaction=True)
def test_przelacznik_aktualizuje_aria_pressed(
    channels_live_server, page: Page, transactional_db
):
    _idz_na_strone(page, _url_autora(channels_live_server))

    przelacznik = page.locator("#bpp-przelacznik-skrotow")
    expect(przelacznik).to_have_attribute("aria-pressed", "true")

    przelacznik.click()
    expect(przelacznik).to_have_attribute("aria-pressed", "false")


@pytest.mark.django_db(transaction=True)
def test_preferencja_przezywa_przeladowanie(
    channels_live_server, page: Page, transactional_db
):
    url = _url_autora(channels_live_server)
    _idz_na_strone(page, url)

    page.locator("#bpp-przelacznik-skrotow").click()
    page.reload(wait_until="domcontentloaded")

    expect(page.locator("#bpp-przelacznik-skrotow")).to_have_attribute(
        "aria-pressed", "false"
    )


# --- WCAG 2.5.7 / 2.1.1: nawigacja po grafie powiązań ----------------------
#
# Samo sprawdzenie widoczności przycisku nie wystarczy: przycisk zostałby
# widoczny, nawet gdyby ktoś odpiął mu handler kliknięcia. Cytoscape.js
# przechowuje żywą instancję na `container._cyreg.cy` (wewnętrzny rejestr
# biblioteki, ale stabilny w praktyce) — czytamy z niej realny stan widoku
# (zoom/pan) PRZED i PO interakcji, więc test faktycznie pada, gdy handler
# zniknie, a nie tylko gdy zniknie sam element z DOM.


def _cy_zoom(page):
    return page.evaluate(
        "document.getElementById('cytoscape-container')._cyreg.cy.zoom()"
    )


def _cy_pan(page):
    return page.evaluate(
        "document.getElementById('cytoscape-container')._cyreg.cy.pan()"
    )


def _czekaj_na_graf(page):
    """Cytoscape inicjalizuje się synchronicznie przy DOMContentLoaded, ale
    czekamy jawnie na `_cyreg`, żeby nie uzależniać testu od kolejności
    ładowania skryptów."""
    page.wait_for_function(
        "document.getElementById('cytoscape-container')"
        " && document.getElementById('cytoscape-container')._cyreg"
        " && document.getElementById('cytoscape-container')._cyreg.cy"
    )


@pytest.mark.django_db(transaction=True)
def test_graf_ma_przyciski_nawigacji_i_jest_fokusowalny(
    channels_live_server, page: Page, transactional_db
):
    _idz_na_strone(page, _url_grafu(channels_live_server))

    kontener = page.locator("#cytoscape-container")
    expect(kontener).to_have_attribute("tabindex", "0")
    expect(page.locator("#graf-nav-dopasuj")).to_be_visible(timeout=10000)


@pytest.mark.django_db(transaction=True)
def test_graf_przycisk_zoom_realnie_zmienia_widok(
    channels_live_server, page: Page, transactional_db
):
    _idz_na_strone(page, _url_grafu(channels_live_server))
    expect(page.locator("#graf-nav-zoom-in")).to_be_visible(timeout=10000)
    _czekaj_na_graf(page)

    zoom_przed = _cy_zoom(page)
    page.locator("#graf-nav-zoom-in").click()
    zoom_po = _cy_zoom(page)

    assert zoom_po > zoom_przed, (
        "klik #graf-nav-zoom-in nie zmienil cy.zoom() -- handler kliknięcia "
        "odpiety albo usuniety?"
    )


@pytest.mark.django_db(transaction=True)
def test_graf_przycisk_kierunkowy_realnie_przesuwa_widok(
    channels_live_server, page: Page, transactional_db
):
    _idz_na_strone(page, _url_grafu(channels_live_server))
    expect(page.locator("#graf-nav-gora")).to_be_visible(timeout=10000)
    _czekaj_na_graf(page)

    pan_przed = _cy_pan(page)
    page.locator("#graf-nav-gora").click()
    pan_po = _cy_pan(page)

    assert pan_po != pan_przed, (
        "klik #graf-nav-gora nie zmienil cy.pan() -- handler kliknięcia "
        "odpiety albo usuniety?"
    )


@pytest.mark.django_db(transaction=True)
def test_graf_strzalka_z_klawiatury_realnie_przesuwa_widok(
    channels_live_server, page: Page, transactional_db
):
    # Dowód wiązania klawiatura -> nawigacja (WCAG 2.1.1): funkcja dostępna
    # myszką jako "przesuń w górę" musi być dostępna też z klawiatury.
    _idz_na_strone(page, _url_grafu(channels_live_server))
    _czekaj_na_graf(page)

    kontener = page.locator("#cytoscape-container")
    kontener.focus()

    pan_przed = _cy_pan(page)
    page.keyboard.press("ArrowUp")
    pan_po = _cy_pan(page)

    assert pan_po != pan_przed, (
        "ArrowUp na sfokusowanym #cytoscape-container nie zmienil cy.pan() "
        "-- obsluzKlawisz odpiety od kontenera?"
    )


@pytest.mark.django_db(transaction=True)
def test_graf_nie_jest_pulapka_klawiaturowa(
    channels_live_server, page: Page, transactional_db
):
    # Handler robi preventDefault WYŁĄCZNIE dla obsłużonych klawiszy. Gdyby
    # blokował wszystko, Tab przestałby wyprowadzać focus — czyli naprawiając
    # 2.1.1 stworzylibyśmy pułapkę klawiaturową i złamalibyśmy 2.1.2.
    _idz_na_strone(page, _url_grafu(channels_live_server))

    kontener = page.locator("#cytoscape-container")
    kontener.focus()
    expect(kontener).to_be_focused()

    page.keyboard.press("Tab")

    assert page.evaluate("document.activeElement.id") != "cytoscape-container"
