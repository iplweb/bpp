import pytest
from model_bakery import baker
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.wait import WebDriverWait

from bpp.models import Rekord, Wydawnictwo_Ciagle
from bpp.tests import select_select2_autocomplete

from django_bpp.selenium_util import LONG_WAIT_TIME, wait_for_page_load

pytestmark = pytest.mark.uruchom_tylko_bez_microsoft_auth


def test_global_search_user(
    channels_live_server,
    splinter_browser,
    transactional_db,
):
    rec = None
    try:
        rec = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test")
        Rekord.objects.full_refresh()

        assert Rekord.objects.count() >= 1
        assert Rekord.objects.filter(tytul_oryginalny__icontains="Test").exists()

        with wait_for_page_load(splinter_browser):
            splinter_browser.visit(channels_live_server.url)

        with wait_for_page_load(splinter_browser):
            select_select2_autocomplete(
                splinter_browser,
                "id_global_nav_value",
                "Test",
                value_before_enter="Rekord",
                wait_for_new_value=False,  # False, bo zmiana wartosci powoduje wczytanie strony
            )

        try:
            WebDriverWait(splinter_browser, LONG_WAIT_TIME).until(
                lambda browser: "Charakter formalny" in browser.html
            )
        except TimeoutException:
            raise TimeoutException(f"Browser.html dump: {splinter_browser.html}")
    finally:
        if rec is not None:
            rec.delete()


def test_global_search_logged_in(
    channels_live_server,
    admin_browser,
    transactional_db,
):
    rec = None
    try:
        browser = admin_browser
        baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test")
        Rekord.objects.full_refresh()

        with wait_for_page_load(browser):
            browser.visit(channels_live_server.url)

        with wait_for_page_load(browser):
            select_select2_autocomplete(
                browser,
                "id_global_nav_value",
                "Test",
                value_before_enter="Rekord",
                wait_for_new_value=False,  # False, bo zmiana wartosci powoduje wczytanie strony
            )

        try:
            WebDriverWait(browser, LONG_WAIT_TIME).until(
                lambda browser: "Charakter formalny" in browser.html
            )
        except TimeoutException:
            raise TimeoutException(f"Browser.html dump: {browser.html}")
    finally:
        if rec is not None:
            rec.delete()


def test_global_search_in_admin(channels_live_server, admin_browser, transactional_db):
    browser = admin_browser
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test")

    with wait_for_page_load(browser):
        browser.visit(channels_live_server.url + "/admin/")

    with wait_for_page_load(browser):
        select_select2_autocomplete(
            browser,
            "id_global_nav_value",
            "Test",
            value_before_enter="ydawnictwo",
            wait_for_new_value=False,  # False, bo zmiana wartosci powoduje wczytanie strony
        )

    browser.wait_for_condition(
        lambda browser: "Zmień wydawnictwo ciągłe" in browser.html,
        timeout=LONG_WAIT_TIME,
    )
