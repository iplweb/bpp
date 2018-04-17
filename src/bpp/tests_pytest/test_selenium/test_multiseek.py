# -*- encoding: utf-8 -*-
from django.urls.base import reverse

from bpp.models.cache import Rekord
from django_bpp.selenium_util import wait_for_page_load


def test_wyrzuc(wydawnictwo_zwarte, live_server, browser):
    browser.visit(
        live_server + reverse("multiseek:index")
    )

    with wait_for_page_load(browser):
        browser.find_by_id("multiseek-szukaj").click()

    browser.execute_script(
        "multiseek.removeFromResults('%s')" % Rekord.objects.all().first().js_safe_pk)

    with wait_for_page_load(browser):
        browser.visit(live_server + reverse("multiseek:results"))

    assert "Z zapytania usunięto" in browser.html

    browser.find_by_id("pokaz-jakie").click()

    browser.execute_script(
        "multiseek.removeFromResults('%s')" % Rekord.objects.all().first().js_safe_pk)

    with wait_for_page_load(browser):
        browser.visit(live_server + reverse("multiseek:results"))

    assert "Z zapytania usunięto" not in browser.html
