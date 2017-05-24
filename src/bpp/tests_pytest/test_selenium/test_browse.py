# -*- encoding: utf-8 -*-
import sys
import time

import pytest
from django.conf import settings
from django.core.urlresolvers import reverse
from model_mommy import mommy
from selenium.webdriver.common.keys import Keys

from bpp.models import Autor, Zrodlo

pytestmark = [pytest.mark.slow, pytest.mark.selenium]

@pytest.fixture
def autorzy_browser(browser, live_server):
    mommy.make(Autor, nazwisko='Atest', imiona='foo')
    browser.visit(live_server + reverse("bpp:browse_autorzy"))
    return browser

def test_autorzy_index(autorzy_browser):
    assert 'Atest' in autorzy_browser.html



def test_autorzy_search_form(autorzy_browser):
    autorzy_browser.fill("search", "Atest")
    autorzy_browser.find_by_name("search").type(Keys.RETURN)
    time.sleep(1)
    assert 'Atest' in autorzy_browser.html

    autorzy_browser.fill("search", "Btest")
    autorzy_browser.find_by_name("search").type(Keys.RETURN)
    time.sleep(1)
    assert 'Atest' not in autorzy_browser.html


def test_autorzy_literki(autorzy_browser):
    literka = autorzy_browser.find_by_id("literka_A")
    literka.click()
    time.sleep(1)
    assert 'Atest' in autorzy_browser.html

    literka = autorzy_browser.find_by_id("literka_B")
    literka.click()
    time.sleep(1)
    assert 'Atest' not in autorzy_browser.html


@pytest.fixture
def zrodla_browser(browser, live_server):
    mommy.make(Zrodlo, nazwa='Atest')
    browser.visit(live_server + reverse("bpp:browse_zrodla"))
    return browser

def test_zrodla_index(zrodla_browser):
    assert 'Atest' in zrodla_browser.html


def test_zrodla_literki(zrodla_browser):
    literka = zrodla_browser.find_by_id("literka_A")
    literka.click()
    time.sleep(1)
    assert 'Atest' in zrodla_browser.html

    literka = zrodla_browser.find_by_id("literka_B")
    literka.click()
    time.sleep(1)
    assert 'Atest' not in zrodla_browser.html


def test_zrodla_search_form(zrodla_browser):
    input = zrodla_browser.find_by_name("search")
    input.type('Atest', Keys.RETURN)
    time.sleep(1)
    assert 'Atest' in zrodla_browser.html

    input = zrodla_browser.find_by_name("search")
    ctrl = Keys.CONTROL
    if sys.platform == 'darwin':
        ctrl = Keys.COMMAND

    input.type(ctrl)
    input.type('a')
    input.type('Btest')
    input.type(Keys.RETURN)
    time.sleep(1)
    assert 'Atest' not in zrodla_browser.html
