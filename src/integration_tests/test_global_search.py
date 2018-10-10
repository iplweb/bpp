from model_mommy import mommy

from bpp.models import Wydawnictwo_Ciagle
from bpp.tests import select_select2_autocomplete
from django_bpp.selenium_util import wait_for_page_load


def test_global_search_user(live_server, browser, transactional_db):
    mommy.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test")

    browser.visit(live_server.url)

    with wait_for_page_load(browser):
        select_select2_autocomplete(
            browser,
            "id_global_nav_value",
            "Test",
            delay_before_enter=0.5,
            delay_after_selection=0.5
        )

    browser.wait_for_condition(
        lambda browser: "Źródło" in browser.html
    )

    assert "Strona WWW" in browser.html


def test_global_search_logged_in(live_server, preauth_admin_browser, transactional_db):
    browser = preauth_admin_browser
    mommy.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test")

    browser.visit(live_server.url)

    with wait_for_page_load(browser):
        select_select2_autocomplete(
            browser,
            "id_global_nav_value",
            "Test",
            delay_before_enter=0.5,
            delay_after_selection=0.5
        )

    browser.wait_for_condition(
        lambda browser: "Źródło" in browser.html
    )

    assert "Strona WWW" in browser.html



def test_global_search_in_admin(live_server, preauth_admin_browser, transactional_db):
    browser = preauth_admin_browser
    mommy.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test")

    browser.visit(live_server.url + "/admin/")

    with wait_for_page_load(browser):
        select_select2_autocomplete(
            browser,
            "id_global_nav_value",
            "Test",
            delay_before_enter=0.5,
            delay_after_selection=0.5
        )

    browser.wait_for_condition(
        lambda browser: "Zmień wydawnictwo ciągłe" in browser.html
    )
