# -*- encoding: utf-8 -*-
import pytest
from selenium.common.exceptions import WebDriverException

from bpp.tests.util import scroll_into_view

ID = "id_tytul_oryginalny"

pytestmark = [pytest.mark.slow, pytest.mark.selenium]


def proper_click(browser, arg):
    # Czy ta metoda jest potrzebna? Kiedyś był bug, który
    # uniemożliwiał kliknięcie elementu, który nei był widoczny
    # na stronie, stąd konieczność przescrollowania do niego
    #
    # 2017.07.18 jest potrzebna (mpasternak)
    #
    scroll_into_view(browser, arg)
    browser.execute_script("document.getElementById('" + arg + "').click()")


def clickButtonBuggyMarionetteDriver(browser, id):
    try:
        browser.execute_script("$('#" + id + "').click()")
    except WebDriverException as e:
        if e.msg.startswith("Failed to find value field"):
            pass
        else:
            raise e


# url = "/admin/"

def assertPopupContains(browser, text, accept=True):
    """Switch to popup, assert it contains at least a part
    of the text, close the popup. Error otherwise.
    """
    alert = browser.driver.switch_to.alert
    if text not in alert.text:
        raise AssertionError("%r not found in %r" % (text, alert.text))
    if accept:
        alert.accept()
