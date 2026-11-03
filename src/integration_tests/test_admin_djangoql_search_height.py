"""Pole wyszukiwania DjangoQL w adminie grappelli nie może być „spłaszczone".

djangoql autoResize liczy wysokość textarei wg modelu content-box, a grappelli
wymusza border-box — bez poprawki w fix-djangoql-css-for-grappelli.css pole
bez nakładki highlight miało 15 px łącznie z paddingiem."""

import pytest
from playwright.sync_api import Page

from django_bpp.playwright_util import wait_for_page_load

# Zwykły input tekstowy grappelli w tym formularzu ma ~25 px; 15 px = bug.
MIN_WYSOKOSC = 22


def _wysokosc_pola(page: Page) -> float:
    page.wait_for_selector("textarea[name=q]", timeout=10000)
    return page.evaluate(
        "() => document.querySelector('textarea[name=q]')"
        "  .getBoundingClientRect().height"
    )


@pytest.mark.parametrize(
    "url",
    [
        # DjangoQLSearchMixin bez naszej nakładki highlight
        "/admin/zglos_publikacje/zgloszenie_publikacji/",
        # BppDjangoQLSearchMixin (z nakładką highlight)
        "/admin/bpp/zrodlo/",
    ],
)
def test_admin_djangoql_search_pole_ma_normalna_wysokosc(
    channels_live_server, admin_page: Page, transactional_db, url
):
    admin_page.goto(channels_live_server.url + url)
    wait_for_page_load(admin_page)
    assert _wysokosc_pola(admin_page) >= MIN_WYSOKOSC


def test_admin_djangoql_search_wysokosc_po_wylaczeniu_ql(
    channels_live_server, admin_page: Page, transactional_db
):
    # Odznaczony przełącznik QL zdejmuje nakładkę highlight (i jej klasę
    # .dql-highlight-input) — pole nadal ma mieć normalną wysokość.
    admin_page.goto(channels_live_server.url + "/admin/bpp/zrodlo/")
    wait_for_page_load(admin_page)
    toggle = admin_page.locator("input.djangoql-toggle")
    toggle.wait_for(timeout=10000)
    if toggle.is_checked():
        toggle.uncheck()
    admin_page.fill("textarea[name=q]", "abc")
    assert _wysokosc_pola(admin_page) >= MIN_WYSOKOSC
