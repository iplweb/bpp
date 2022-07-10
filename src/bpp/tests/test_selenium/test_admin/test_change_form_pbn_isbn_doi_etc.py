import time

import pytest
from django.urls import reverse
from selenium.common.exceptions import NoAlertPresentException
from selenium.webdriver.common.keys import Keys

from fixtures import pbn_pageable_json, pbn_publication_json
from pbn_api.client import PBN_GET_PUBLICATION_BY_ID_URL, PBN_SEARCH_PUBLICATIONS_URL
from pbn_api.models import Publication
from pbn_api.models.publication import STATUS_ACTIVE

from bpp.tests import (
    proper_click_element,
    rozwin_ekstra_informacje_na_stronie_edycji_wydawnictwa,
)

from django_bpp.selenium_util import VERY_SHORT_WAIT_TIME, wait_for_page_load


@pytest.mark.parametrize("field_name", ["isbn", "e_isbn"])
def test_change_form_get_pbn_by_isbn_or_eisbn_via_api_pub_jest_w_api(
    admin_browser,
    asgi_live_server,
    field_name,
    pbn_serwer,
):
    url = reverse("admin:bpp_wydawnictwo_zwarte_add")
    with wait_for_page_load(admin_browser):
        admin_browser.visit(asgi_live_server.url + url)

    ROK = "2222"
    ISBN = "123"
    UID_REKORDU = "aosidjfoasidjfasdfghjksl"

    rozwin_ekstra_informacje_na_stronie_edycji_wydawnictwa(admin_browser)

    pub1 = pbn_publication_json(ROK, mongoId=UID_REKORDU, isbn=ISBN)
    pbn_serwer.expect_request(PBN_SEARCH_PUBLICATIONS_URL).respond_with_json(
        pbn_pageable_json([pub1])
    )
    pbn_serwer.expect_request(
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=UID_REKORDU)
    ).respond_with_json(pub1)

    admin_browser.find_by_id("id_tytul_oryginalny").fill("nie istotny")
    admin_browser.find_by_id("id_rok").fill(ROK)
    admin_browser.find_by_id(f"id_{field_name}").fill(ISBN)

    if not admin_browser.find_by_id("id_isbn_pbn_get"):
        raise Exception("Nie mozna znalexc elementu")

    btn = admin_browser.find_by_id("id_isbn_pbn_get")
    proper_click_element(admin_browser, btn)

    time.sleep(VERY_SHORT_WAIT_TIME)

    admin_browser.find_by_css("input.select2-search__field").type(Keys.ENTER)
    time.sleep(VERY_SHORT_WAIT_TIME)

    assert admin_browser.find_by_id("id_pbn_uid").value == UID_REKORDU


@pytest.mark.parametrize("field_name", ["isbn", "e_isbn"])
def test_change_form_get_pbn_by_isbn_or_eisbn_via_api_pub_jest_w_lokalnej_bazie(
    admin_browser, asgi_live_server, field_name, pbn_serwer, transactional_db
):
    url = reverse("admin:bpp_wydawnictwo_zwarte_add")
    with wait_for_page_load(admin_browser):
        admin_browser.visit(asgi_live_server.url + url)

    ROK = "2222"
    ISBN = "123"
    UID_REKORDU = "aosidjfoasidjfasdfghjksl"

    try:
        pub = Publication.objects.create(
            mongoId=UID_REKORDU,
            verificationLevel="moze",
            verified=True,
            status=STATUS_ACTIVE,
            versions=[
                {
                    "current": True,
                    "object": {"year": ROK, "isbn": ISBN, "title": "Ten tego"},
                }
            ],
        )

        rozwin_ekstra_informacje_na_stronie_edycji_wydawnictwa(admin_browser)

        pbn_serwer.expect_request(PBN_SEARCH_PUBLICATIONS_URL).respond_with_json(
            pbn_pageable_json([])
        )

        admin_browser.find_by_id("id_tytul_oryginalny").fill("nie istotny")
        admin_browser.find_by_id("id_rok").fill(ROK)
        admin_browser.find_by_id(f"id_{field_name}").fill(ISBN)

        if not admin_browser.find_by_id("id_isbn_pbn_get"):
            raise Exception("Nie mozna znalexc elementu")

        btn = admin_browser.find_by_id("id_isbn_pbn_get")
        proper_click_element(admin_browser, btn)

        time.sleep(VERY_SHORT_WAIT_TIME)

        admin_browser.find_by_css("input.select2-search__field").type(Keys.ENTER)

        assert admin_browser.find_by_id("id_pbn_uid").value == UID_REKORDU
    finally:
        pub.delete()


@pytest.mark.parametrize("wydawnictwo", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_change_form_get_pbn_by_doi_via_api_jest_w_api(
    admin_browser, asgi_live_server, wydawnictwo, pbn_serwer
):
    url = reverse(f"admin:bpp_{wydawnictwo}_add")
    with wait_for_page_load(admin_browser):
        admin_browser.visit(asgi_live_server.url + url)

    ROK = "2222"
    DOI = "123"
    UID_REKORDU = "aosidjfoasidjfasdfghjksl"

    pub1 = pbn_publication_json(ROK, mongoId=UID_REKORDU, doi=DOI)
    pbn_serwer.expect_request(PBN_SEARCH_PUBLICATIONS_URL).respond_with_json(
        pbn_pageable_json([pub1])
    )
    pbn_serwer.expect_request(
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=UID_REKORDU)
    ).respond_with_json(pub1)

    rozwin_ekstra_informacje_na_stronie_edycji_wydawnictwa(admin_browser)

    admin_browser.find_by_id("id_tytul_oryginalny").fill("nie istotny")
    admin_browser.find_by_id("id_rok").fill(ROK)
    admin_browser.find_by_id("id_doi").fill(DOI)

    if not admin_browser.find_by_id("id_doi_pbn_get"):
        raise Exception("Nie mozna znalexc elementu")

    btn = admin_browser.find_by_id("id_doi_pbn_get")
    proper_click_element(admin_browser, btn)

    time.sleep(VERY_SHORT_WAIT_TIME)

    with pytest.raises(NoAlertPresentException):
        admin_browser.driver.switch_to.alert

    admin_browser.find_by_css("input.select2-search__field").type(Keys.ENTER)

    assert admin_browser.find_by_id("id_pbn_uid").value == UID_REKORDU


@pytest.mark.parametrize("wydawnictwo", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_change_form_get_pbn_by_doi_via_api_nie_ma_w_api_jest_w_bazie(
    admin_browser, asgi_live_server, wydawnictwo, pbn_serwer, transactional_db
):
    url = reverse(f"admin:bpp_{wydawnictwo}_add")
    with wait_for_page_load(admin_browser):
        admin_browser.visit(asgi_live_server.url + url)

    ROK = "2222"
    DOI = "123"
    UID_REKORDU = "aosidjfoasidjfasdfghjksl"

    try:
        res = Publication.objects.create(
            mongoId=UID_REKORDU,
            verificationLevel="moze",
            verified=True,
            status="ACTIVE",
            versions=[
                {
                    "current": True,
                    "object": {"year": ROK, "doi": DOI, "title": "Ten tego"},
                }
            ],
        )
        pbn_serwer.expect_request(PBN_SEARCH_PUBLICATIONS_URL).respond_with_json(
            pbn_pageable_json([])
        )

        rozwin_ekstra_informacje_na_stronie_edycji_wydawnictwa(admin_browser)

        admin_browser.find_by_id("id_tytul_oryginalny").fill("nie istotny")
        admin_browser.find_by_id("id_rok").fill(ROK)
        admin_browser.find_by_id("id_doi").fill(DOI)

        if not admin_browser.find_by_id("id_doi_pbn_get"):
            raise Exception("Nie mozna znalexc elementu")

        btn = admin_browser.find_by_id("id_doi_pbn_get")
        proper_click_element(admin_browser, btn)

        time.sleep(VERY_SHORT_WAIT_TIME)

        with pytest.raises(NoAlertPresentException):
            admin_browser.driver.switch_to.alert

        time.sleep(VERY_SHORT_WAIT_TIME)

        admin_browser.find_by_css("input.select2-search__field").type(Keys.ENTER)
        time.sleep(VERY_SHORT_WAIT_TIME)

        assert admin_browser.find_by_id("id_pbn_uid").value == UID_REKORDU
    finally:
        res.delete()
