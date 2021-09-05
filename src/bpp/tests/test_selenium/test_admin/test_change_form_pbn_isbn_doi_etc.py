import time

import pytest
from django.urls import reverse
from model_mommy import mommy
from selenium.common.exceptions import NoAlertPresentException
from selenium.webdriver.common.keys import Keys

from pbn_api.models import Publication

from bpp.models import Uczelnia
from bpp.tests import (
    proper_click_element,
    rozwin_ekstra_informacje_na_stronie_edycji_wydawnictwa,
)

from django_bpp.selenium_util import wait_for_page_load


@pytest.mark.parametrize("field_name", ["isbn", "e_isbn"])
def test_change_form_get_pbn_by_isbn_or_eisbn_via_api(
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

        rozwin_ekstra_informacje_na_stronie_edycji_wydawnictwa(admin_browser)

        admin_browser.find_by_id("id_tytul_oryginalny").fill("nie istotny")
        admin_browser.find_by_id("id_rok").fill(ROK)
        admin_browser.find_by_id(f"id_{field_name}").fill(ISBN)

        if not admin_browser.find_by_id("id_isbn_pbn_get"):
            raise Exception("Nie mozna znalexc elementu")

        btn = admin_browser.find_by_id("id_isbn_pbn_get")
        proper_click_element(admin_browser, btn)

        time.sleep(0.5)

        admin_browser.switch_to.active_element.send_keys(Keys.ENTER)

        assert admin_browser.find_by_id("id_pbn_uid").value == UID_REKORDU
    finally:
        u.delete()


@pytest.mark.parametrize("wydawnictwo", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_change_form_get_pbn_by_doi_via_api(
    admin_browser,
    asgi_live_server,
    wydawnictwo,
    transactional_db,
):
    u = mommy.make(Uczelnia)

    try:
        url = reverse(f"admin:bpp_{wydawnictwo}_add")
        with wait_for_page_load(admin_browser):
            admin_browser.visit(asgi_live_server.url + url)

        ROK = "2222"
        DOI = "123"
        UID_REKORDU = "aosidjfoasidjf"

        Publication.objects.create(
            mongoId=UID_REKORDU,
            verificationLevel="moze",
            verified=True,
            versions=[
                {
                    "current": True,
                    "object": {"year": ROK, "doi": DOI, "title": "Ten tego"},
                }
            ],
        )

        rozwin_ekstra_informacje_na_stronie_edycji_wydawnictwa(admin_browser)

        admin_browser.find_by_id("id_tytul_oryginalny").fill("nie istotny")
        admin_browser.find_by_id("id_rok").fill(ROK)
        admin_browser.find_by_id("id_doi").fill(DOI)

        if not admin_browser.find_by_id("id_doi_pbn_get"):
            raise Exception("Nie mozna znalexc elementu")

        btn = admin_browser.find_by_id("id_doi_pbn_get")
        proper_click_element(admin_browser, btn)

        time.sleep(0.5)

        with pytest.raises(NoAlertPresentException):
            admin_browser.driver.switch_to.alert

        admin_browser.switch_to.active_element.send_keys(Keys.ENTER)

        assert admin_browser.find_by_id("id_pbn_uid").value == UID_REKORDU
    finally:
        u.delete()
