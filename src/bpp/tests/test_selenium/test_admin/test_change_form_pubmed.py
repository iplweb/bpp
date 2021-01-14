import pytest
from django.urls import reverse
from selenium.webdriver.support.expected_conditions import alert_is_present

from bpp.tests import assertPopupContains, show_element
from bpp.views.api import const

from django_bpp.selenium_util import wait_for


@pytest.mark.parametrize(
    "tytul,wynik",
    [
        (const.PUBMED_TITLE_NONEXISTENT, const.PUBMED_PO_TYTULE_BRAK),
        (const.PUBMED_TITLE_MULTIPLE, const.PUBMED_PO_TYTULE_WIELE),
        ("", "Aby wykonać zapytanie, potrzebny jest tytuł w polu"),
        ("   ", const.PUBMED_BRAK_PARAMETRU),
    ],
)
@pytest.mark.parametrize(
    "url",
    [
        "wydawnictwo_zwarte",
        "wydawnictwo_ciagle",
    ],
)
def test_change_form_pubmed_brak_takiej_pracy(
    admin_browser, asgi_live_server, url, tytul, wynik
):
    url = reverse(f"admin:bpp_{url}_add")
    admin_browser.visit(asgi_live_server.url + url)
    admin_browser.find_by_id("id_tytul_oryginalny").fill(tytul)
    for elem in admin_browser.find_by_tag("h2")[:3]:
        show_element(admin_browser, elem)  # ._element)
        elem.click()
    btn = admin_browser.find_by_id("id_pubmed_id_get")
    show_element(admin_browser, btn)
    btn.click()

    wait_for(lambda: alert_is_present()(admin_browser.driver))
    assertPopupContains(admin_browser, wynik)
