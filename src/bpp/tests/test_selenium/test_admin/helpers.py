# -*- encoding: utf-8 -*-
import time

import pytest
from selenium.common.exceptions import WebDriverException

from bpp.tests.util import scroll_into_view

ID = "id_tytul_oryginalny"

pytestmark = [pytest.mark.slow, pytest.mark.selenium]


def proper_click(browser, arg):
    scroll_into_view(browser, arg)
    browser.execute_script(f"document.getElementById('{arg}').click()")


def assertPopupContains(browser, text, accept=True):
    """Switch to popup, assert it contains at least a part
    of the text, close the popup. Error otherwise.
    """
    alert = browser.driver.switch_to.alert
    if text not in alert.text:
        raise AssertionError("%r not found in %r" % (text, alert.text))
    if accept:
        alert.accept()
