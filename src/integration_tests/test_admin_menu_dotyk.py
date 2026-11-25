"""FD#626: menu modułu redagowania na ekranie dotykowym.

Podmenu otwiera tam ``:hover``. Na dotyku „najechanie” dorabia przeglądarka
po stuknięciu i trzyma je do następnego stuknięcia w coś klikalnego: podmenu
nie dało się zamknąć ponownym stuknięciem pozycji, a na iOS — także
stuknięciem w puste miejsce strony. Teraz stuknięcie pozycji przełącza klasę
``over`` (``src/bpp/static/bpp/js/admin-menu-dotyk.js``), a stuknięcie poza
menu ją zdejmuje.
"""

import pytest
from playwright.sync_api import Page, expect

from django_bpp.playwright_util import wait_for_page_load

TABLET = dict(
    viewport={"width": 1080, "height": 810},
    device_scale_factor=2,
    is_mobile=True,
    has_touch=True,
)

POZYCJA_Z_PODMENU = "#navigation-menu > li:has(> ul)"


def _otworz_redagowanie(page: Page, url: str):
    page.goto(url + "/admin/")
    wait_for_page_load(page)
    page.evaluate("if (typeof Cookielaw !== 'undefined') { Cookielaw.accept(); }")
    wait_for_page_load(page)
    pozycja = page.locator(POZYCJA_Z_PODMENU).first
    pozycja.wait_for(state="visible")
    return pozycja, pozycja.locator("> ul")


@pytest.mark.browser_context_args(**TABLET)
def test_stukniecie_otwiera_podmenu_i_dziala_link(
    channels_live_server, admin_page: Page
):
    pozycja, podmenu = _otworz_redagowanie(admin_page, channels_live_server.url)

    pozycja.locator("> a").tap()
    expect(podmenu).to_be_visible()
    admin_page.wait_for_timeout(600)
    expect(podmenu).to_be_visible()

    link = podmenu.locator("li > a[href]:not([href='#'])").first
    cel = link.get_attribute("href")
    link.tap()
    admin_page.wait_for_url(f"**{cel}")


@pytest.mark.browser_context_args(**TABLET)
def test_ponowne_stukniecie_i_stukniecie_obok_zamyka_podmenu(
    channels_live_server, admin_page: Page
):
    pozycja, podmenu = _otworz_redagowanie(admin_page, channels_live_server.url)

    pozycja.locator("> a").tap()
    expect(podmenu).to_be_visible()

    # Ta sama pozycja drugi raz — zamyka.
    pozycja.locator("> a").tap()
    expect(podmenu).to_be_hidden()

    # Otwórz ponownie i stuknij w treść strony.
    pozycja.locator("> a").tap()
    expect(podmenu).to_be_visible()
    admin_page.locator("#grp-content h1").first.tap()
    expect(podmenu).to_be_hidden()

    # Sąsiednia pozycja przełącza podmenu.
    druga = admin_page.locator(POZYCJA_Z_PODMENU).nth(1)
    pozycja.locator("> a").tap()
    expect(podmenu).to_be_visible()
    druga.locator("> a").tap()
    expect(druga.locator("> ul")).to_be_visible()
    expect(podmenu).to_be_hidden()
