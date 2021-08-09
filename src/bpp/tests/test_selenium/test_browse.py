# -*- encoding: utf-8 -*-

import pytest
from selenium.webdriver.support.wait import WebDriverWait

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from model_mommy import mommy
from selenium.webdriver.common.keys import Keys

from bpp.models import Autor, Zrodlo

from django_bpp.selenium_util import SHORT_WAIT_TIME, wait_for_page_load

pytestmark = [pytest.mark.slow, pytest.mark.selenium]


@pytest.fixture(scope="function")
def autorzy_browser(browser, live_server):
    mommy.make(Autor, nazwisko="Atest", imiona="foo")
    browser.visit(live_server + reverse("bpp:browse_autorzy"))
    yield browser
    browser.quit()


def test_autorzy_index(autorzy_browser):
    assert "Atest" in autorzy_browser.html


def test_autorzy_search_form(autorzy_browser):
    autorzy_browser.fill("search", "Atest")
    autorzy_browser.find_by_name("search").type(Keys.RETURN)
    autorzy_browser.wait_for_condition(lambda browser: "Atest" in browser.html)

    autorzy_browser.reload()
    autorzy_browser.fill("search", "Btest")
    autorzy_browser.find_by_name("search").type(Keys.RETURN)
    autorzy_browser.wait_for_condition(lambda browser: "Atest" not in browser.html)


def test_autorzy_literki(autorzy_browser):
    literka = autorzy_browser.find_by_id("literka_A")

    with wait_for_page_load(autorzy_browser):
        literka.click()
    assert "Atest" in autorzy_browser.html

    literka = autorzy_browser.find_by_id("literka_B")
    with wait_for_page_load(autorzy_browser):
        literka.click()
    assert "Atest" not in autorzy_browser.html


@pytest.fixture(scope="function")
def zrodla_browser(browser, live_server):
    mommy.make(Zrodlo, nazwa="Atest")
    browser.visit(live_server + reverse("bpp:browse_zrodla"))
    yield browser
    browser.quit()


def test_zrodla_index(zrodla_browser):
    assert "Atest" in zrodla_browser.html


def test_zrodla_literki(zrodla_browser):
    literka = zrodla_browser.find_by_id("literka_A")

    with wait_for_page_load(zrodla_browser):
        literka.click()
    assert "Atest" in zrodla_browser.html

    literka = zrodla_browser.find_by_id("literka_B")
    with wait_for_page_load(zrodla_browser):
        literka.click()
    assert "Atest" not in zrodla_browser.html


def test_zrodla_search_form(zrodla_browser):
    input = zrodla_browser.find_by_name("search")
    input.type("Atest")
    input.type(Keys.RETURN)
    WebDriverWait(zrodla_browser.driver, SHORT_WAIT_TIME).until(
        lambda x: "Atest" in zrodla_browser.html
    )

    zrodla_browser.reload()
    input = zrodla_browser.find_by_name("search")
    input.fill("Btest")
    input.type(Keys.RETURN)

    WebDriverWait(zrodla_browser.driver, SHORT_WAIT_TIME).until(
        lambda x: "Atest" not in zrodla_browser.html
    )
