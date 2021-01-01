# -*- encoding: utf-8 -*-

from bpp.tests import show_element

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

import pytest
from mock import Mock
from selenium.webdriver.support.expected_conditions import alert_is_present

from bpp.tests.util import assertPopupContains, scroll_into_view

from django_bpp.selenium_util import wait_for, wait_for_page_load

ID = "id_tytul_oryginalny"

pytestmark = [pytest.mark.slow, pytest.mark.selenium]


@pytest.fixture(scope="function")
def browser_z_wydawnictwem(admin_browser, asgi_live_server, wydawnictwo_ciagle):
    browser = admin_browser
    with wait_for_page_load(browser):
        browser.visit(
            asgi_live_server.url
            + reverse(
                "admin:bpp_wydawnictwo_ciagle_change", args=(wydawnictwo_ciagle.pk,)
            )
        )
    return browser


def test_admin_get_wos_information_clarivate_brak_danych(browser_z_wydawnictwem):
    browser = browser_z_wydawnictwem
    elem = browser.find_by_id("id_liczba_cytowan_get")
    show_element(browser, elem)
    elem.click()

    def _():
        try:
            assertPopupContains(browser, "DOI")
            return True
        except AssertionError:
            pass

    wait_for(_)


def test_admin_get_wos_information_clarivate_pmid(
    uczelnia, mocker, browser_z_wydawnictwem
):
    from mock import Mock

    m = Mock()
    m.query_single = Mock(return_value={"timesCited": "31337"})
    mocker.patch("bpp.models.struktura.Uczelnia.wosclient", return_value=m)

    browser = browser_z_wydawnictwem
    browser.find_by_id("id_pubmed_id").type("31337")
    scroll_into_view(browser_z_wydawnictwem, "id_liczba_cytowan_get")
    browser.find_by_id("id_liczba_cytowan_get").click()
    wait_for(lambda: browser.find_by_id("id_liczba_cytowan_get").value == "Pobrano!")
    assert browser.find_by_id("id_liczba_cytowan_get").value == "Pobrano!"
    assert browser.find_by_id("id_liczba_cytowan").value == "31337"


def test_admin_get_wos_information_clarivate_err(
    uczelnia, browser_z_wydawnictwem, mocker
):
    m = Mock()
    m.query_single = Mock(side_effect=Exception("lel"))
    mocker.patch("bpp.models.struktura.Uczelnia.wosclient", return_value=m)

    browser = browser_z_wydawnictwem
    browser.find_by_id("id_pubmed_id").type("31337")
    scroll_into_view(browser_z_wydawnictwem, "id_liczba_cytowan_get")
    browser.find_by_id("id_liczba_cytowan_get").click()
    wait_for(lambda: alert_is_present()(browser.driver))
    assertPopupContains(browser, "lel")


def test_admin_get_wos_information_clarivate_misconfigured(
    uczelnia, browser_z_wydawnictwem, mocker
):
    uczelnia.clarivate_password = uczelnia.clarivate_username = ""
    uczelnia.save()

    browser = browser_z_wydawnictwem
    browser.find_by_id("id_pubmed_id").type("31337")
    scroll_into_view(browser_z_wydawnictwem, "id_liczba_cytowan_get")
    browser.find_by_id("id_liczba_cytowan_get").click()
    wait_for(lambda: alert_is_present()(browser.driver))
    assertPopupContains(browser, "Brak użytkownika API")

    uczelnia.clarivate_username = "fa"
    uczelnia.save()

    browser.find_by_id("id_liczba_cytowan_get").click()
    wait_for(lambda: alert_is_present()(browser.driver))
    assertPopupContains(browser, "Brak hasła do API")
