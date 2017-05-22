# -*- encoding: utf-8 -*-

import pytest
from selenium.common.exceptions import NoAlertPresentException


def test_zmiany_formularza(preauth_browser, live_server):
    preauth_browser.visit(live_server + '/password_change/')
    elem = preauth_browser.find_by_id("id_old_password")[0]
    elem.type("123348u3")

    link = preauth_browser.find_link_by_href("/bpp/zrodla/")
    link[0].click()

    with pytest.raises(NoAlertPresentException):
        preauth_browser.get_alert()
