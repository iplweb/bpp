import time

import pytest
from django.urls import reverse
from model_mommy import mommy
from selenium.webdriver.common.keys import Keys

from pbn_api.models import Publication

from bpp.models import Uczelnia
from bpp.tests import proper_click_element, show_element

from django_bpp.selenium_util import wait_for_page_load


@pytest.mark.parametrize("field_name", ["isbn", "e_isbn"])
def test_change_form_pbn_isbn(
    admin_browser, asgi_live_server, transactional_db, field_name
):
    u = mommy.make(Uczelnia)

    try:
        url = reverse("admin:bpp_wydawnictwo_zwarte_add")
        with wait_for_page_load(admin_browser):
            admin_browser.visit(asgi_live_server.url + url)

        ROK = "2222"
        ISBN = "123"
        UID_REKORDU = "aosidjfoasidjf"

        Publication.objects.create(
            mongoId=UID_REKORDU,
            verificationLevel="moze",
            verified=True,
            versions=[
                {
                    "current": True,
                    "object": {"year": ROK, "isbn": ISBN, "title": "Ten tego"},
                }
            ],
        )

        admin_browser.find_by_id("id_tytul_oryginalny").fill("nie istotny")
        admin_browser.find_by_id("id_rok").fill(ROK)
        admin_browser.find_by_id(f"id_{field_name}").fill(ISBN)

        for elem in admin_browser.find_by_tag("h2")[:3]:
            show_element(admin_browser, elem)  # ._element)
            elem.click()

        if not admin_browser.find_by_id("id_isbn_pbn_get"):
            raise Exception("Nie mozna znalexc elementu")

        btn = admin_browser.find_by_id("id_isbn_pbn_get")
        proper_click_element(admin_browser, btn)

        time.sleep(0.5)

        admin_browser.switch_to.active_element.send_keys(Keys.ENTER)

        assert admin_browser.find_by_id("id_pbn_uid").value == UID_REKORDU
    finally:
        u.delete()
