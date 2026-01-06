"""
Tests for admin metadata parsing functionality.

This module contains Selenium tests that verify:
- Year extraction from metadata fields (miejsce_i_rok, informacje)
- Year population from parent publications (wydawnictwo_nadrzedne)
"""

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

import pytest

from bpp.const import CHARAKTER_OGOLNY_KSIAZKA
from bpp.models import Charakter_Formalny
from bpp.tests import proper_click_by_id, proper_click_element
from bpp.tests.util import select_select2_autocomplete
from django_bpp.selenium_util import wait_for_page_load

pytestmark = [pytest.mark.slow, pytest.mark.selenium]


@pytest.mark.django_db
def test_admin_wydawnictwo_zwarte_uzupelnij_rok(
    wydawnictwo_zwarte, admin_browser, channels_live_server, transactional_db
):
    """
    Test year extraction from miejsce_i_rok field and parent publication.

    :type admin_browser: splinter.driver.webdriver.remote.WebDriver
    """
    browser = admin_browser

    browser.visit(
        channels_live_server.url + reverse("admin:bpp_wydawnictwo_zwarte_add")
    )

    rok = browser.find_by_id("id_rok")
    button = browser.find_by_id("id_rok_button")

    assert rok.value == ""

    browser.fill("miejsce_i_rok", "Lublin 2002")

    proper_click_element(browser, button)

    browser.wait_for_condition(
        lambda browser: browser.find_by_id("id_rok").value == "2002"
    )

    chf = Charakter_Formalny.objects.create(
        nazwa="charakter", skrot="ch", charakter_ogolny=CHARAKTER_OGOLNY_KSIAZKA
    )

    wydawnictwo_zwarte.rok = 1997
    wydawnictwo_zwarte.charakter_formalny = chf
    wydawnictwo_zwarte.save()

    select_select2_autocomplete(
        browser, "id_wydawnictwo_nadrzedne", "Wydawnictwo Zwarte"
    )

    browser.fill("rok", "")
    proper_click_element(browser, button)
    browser.wait_for_condition(
        lambda browser: browser.find_by_id("id_rok").value == "2002"
    )

    browser.fill("miejsce_i_rok", "")
    proper_click_element(browser, button)
    browser.wait_for_condition(
        lambda browser: browser.find_by_id("id_rok").value == "1997"
    )


def test_admin_wydawnictwo_ciagle_uzupelnij_rok(admin_browser, channels_live_server):
    """
    Test year extraction from informacje field.

    :type admin_browser: splinter.driver.webdriver.remote.WebDriver
    """
    browser = admin_browser

    with wait_for_page_load(browser):
        browser.visit(
            channels_live_server.url + reverse("admin:bpp_wydawnictwo_ciagle_add")
        )
    browser.fill("informacje", "Lublin 2002 test")
    elem = browser.find_by_id("id_rok_button")
    proper_click_element(browser, elem)

    browser.wait_for_condition(
        lambda browser: browser.find_by_id("id_rok").value == "2002"
    )

    browser.fill("informacje", "")
    proper_click_by_id(browser, "id_rok_button")
    browser.wait_for_condition(
        lambda browser: browser.find_by_id("id_rok_button").value == "Brak danych"
    )
