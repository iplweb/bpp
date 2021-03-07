# -*- encoding: utf-8 -*-
import pytest
from django.urls.base import reverse

from bpp.models.cache import Rekord
from django_bpp.selenium_util import wait_for, wait_for_page_load


@pytest.fixture
def multiseek_browser(browser, live_server):
    browser.visit(live_server + reverse("multiseek:index"))
    return browser


def test_wyrzuc(wydawnictwo_zwarte, multiseek_browser, live_server):
    browser = multiseek_browser

    with wait_for_page_load(browser):
        browser.find_by_id("multiseek-szukaj").click()

    browser.execute_script(
        "multiseek.removeFromResults('%s')" % Rekord.objects.all().first().js_safe_pk
    )

    # Poczekaj czy element został skreślony
    wait_for(
        lambda: browser.find_by_css(".multiseek-element")["style"].find("line-through")
        != -1,
    )

    with wait_for_page_load(browser):
        browser.visit(live_server + reverse("multiseek:results"))

    assert "Z zapytania usunięto" in browser.html

    browser.find_by_id("pokaz-jakie").click()

    browser.execute_script(
        "multiseek.removeFromResults('%s')" % Rekord.objects.all().first().js_safe_pk
    )

    # Poczekaj czy element został od-kreślony
    wait_for(
        lambda: browser.find_by_css(".multiseek-element")["style"].find("line-through")
        == -1
    )

    with wait_for_page_load(browser):
        browser.visit(live_server + reverse("multiseek:results"))

    assert "Z zapytania usunięto" not in browser.html


@pytest.mark.django_db
def test_index_copernicus_schowany(multiseek_browser, uczelnia):
    uczelnia.pokazuj_index_copernicus = False
    uczelnia.save()

    multiseek_browser.reload()

    assert "Index Copernicus" not in multiseek_browser.html


@pytest.mark.django_db
def test_index_copernicus_widoczny(multiseek_browser, uczelnia):
    uczelnia.pokazuj_index_copernicus = True
    uczelnia.save()

    multiseek_browser.reload()
    assert "Index Copernicus" in multiseek_browser.html


def test_szukaj(multiseek_browser):
    with wait_for_page_load(multiseek_browser):
        multiseek_browser.find_by_id("multiseek-szukaj").click()
    assert "błąd serwera" not in multiseek_browser.html
