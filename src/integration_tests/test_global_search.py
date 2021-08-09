from model_mommy import mommy
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.wait import WebDriverWait

from bpp.models import Rekord, Wydawnictwo_Ciagle
from bpp.tests import select_select2_autocomplete

from django_bpp.selenium_util import LONG_WAIT_TIME, wait_for_page_load


def test_global_search_user(asgi_live_server, browser, transactional_db, with_cache):
    rec = None
    try:
        rec = mommy.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test")
        [x.zaktualizuj_cache() for x in Rekord.objects.all()]

        assert Rekord.objects.count() >= 1
        assert Rekord.objects.filter(tytul_oryginalny__icontains="Test").exists()

        with wait_for_page_load(browser):
            browser.visit(asgi_live_server.url)

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
                lambda browser: "Strona WWW" in browser.html
            )
        except TimeoutException:
            raise TimeoutException(f"Browser.html dump: {browser.html}")
    finally:
        if rec is not None:
            rec.delete()


def test_global_search_logged_in(
    asgi_live_server, admin_browser, transactional_db, with_cache
):
    rec = None
    try:
        browser = admin_browser
        mommy.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test")
        [x.zaktualizuj_cache() for x in Rekord.objects.all()]

        with wait_for_page_load(browser):
            browser.visit(asgi_live_server.url)

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
                lambda browser: "Strona WWW" in browser.html
            )
        except TimeoutException:
            raise TimeoutException(f"Browser.html dump: {browser.html}")
    finally:
        if rec is not None:
            rec.delete()


def test_global_search_in_admin(asgi_live_server, admin_browser, transactional_db):
    browser = admin_browser
    mommy.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test")

    with wait_for_page_load(browser):
        browser.visit(asgi_live_server.url + "/admin/")

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
