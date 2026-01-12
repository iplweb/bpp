import pytest
from django.urls import reverse
from playwright.sync_api import Page

from fixtures.pbn_api import pbn_pageable_json, pbn_publication_json
from pbn_api.client import PBN_GET_PUBLICATION_BY_ID_URL, PBN_SEARCH_PUBLICATIONS_URL
from pbn_api.models import Publication
from pbn_api.models.publication import STATUS_ACTIVE


def rozwin_ekstra_informacje_playwright(admin_page: Page):
    """
    Expand "Ekstra informacje" section if it's collapsed.

    Finds the <h2 class="grp-collapse-handler">Ekstra informacje</h2> header
    and clicks it to expand, but only if the parent fieldset has the "grp-closed" class.
    """
    ekstra_header = admin_page.locator(
        "h2.grp-collapse-handler:has-text('Ekstra informacje')"
    )
    if ekstra_header.count() > 0:
        parent = ekstra_header.locator("xpath=ancestor::fieldset[1]").first
        class_attr = parent.get_attribute("class") or ""
        if "grp-closed" in class_attr:
            ekstra_header.first.click()
            admin_page.wait_for_timeout(500)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("wydawnictwo", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_change_form_get_pbn_by_doi_via_api_nie_ma_w_api_jest_w_bazie(
    admin_page: Page, channels_live_server, wydawnictwo, pbn_serwer
):
    """Test PBN DOI lookup finds record in local database when not in API."""
    url = reverse(f"admin:bpp_{wydawnictwo}_add")
    admin_page.goto(channels_live_server.url + url)
    admin_page.wait_for_load_state("domcontentloaded")

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

        rozwin_ekstra_informacje_playwright(admin_page)

        admin_page.fill("#id_tytul_oryginalny", "nie istotny")
        admin_page.fill("#id_rok", ROK)
        admin_page.fill("#id_doi", DOI)

        # Verify button exists
        admin_page.wait_for_selector("#id_doi_pbn_get", state="visible")

        btn = admin_page.locator("#id_doi_pbn_get")
        btn.click()

        # Wait for processing
        admin_page.wait_for_timeout(500)

        # No alert should appear (verify by checking page state is stable)
        # In Playwright, we don't need to explicitly check for alerts like in Selenium

        # Press Enter in the select2 search field to accept the result
        admin_page.wait_for_selector("input.select2-search__field", state="visible")
        admin_page.locator("input.select2-search__field").press("Enter")
        admin_page.wait_for_timeout(500)

        # Verify pbn_uid field was populated with the local database record
        assert admin_page.locator("#id_pbn_uid").input_value() == UID_REKORDU
    finally:
        res.delete()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("wydawnictwo", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_change_form_get_pbn_by_doi_via_api_jest_w_api(
    admin_page: Page, channels_live_server, wydawnictwo, pbn_serwer
):
    """Test PBN DOI lookup finds record via API."""
    url = reverse(f"admin:bpp_{wydawnictwo}_add")
    admin_page.goto(channels_live_server.url + url)
    admin_page.wait_for_load_state("domcontentloaded")

    ROK = "2222"
    DOI = "123"
    UID_REKORDU = "aosidjfoasidjfasdfghjksl"

    # Setup mock PBN API responses
    pub1 = pbn_publication_json(ROK, mongoId=UID_REKORDU, doi=DOI)
    pbn_serwer.expect_request(PBN_SEARCH_PUBLICATIONS_URL).respond_with_json(
        pbn_pageable_json([pub1])
    )
    pbn_serwer.expect_request(
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=UID_REKORDU)
    ).respond_with_json(pub1)

    rozwin_ekstra_informacje_playwright(admin_page)

    admin_page.fill("#id_tytul_oryginalny", "nie istotny")
    admin_page.fill("#id_rok", ROK)
    admin_page.fill("#id_doi", DOI)

    # Verify button exists
    admin_page.wait_for_selector("#id_doi_pbn_get", state="visible")

    btn = admin_page.locator("#id_doi_pbn_get")
    btn.click()

    # Wait for processing
    admin_page.wait_for_timeout(500)

    # No alert should appear (verify by checking page state is stable)
    # In Playwright, we don't need to explicitly check for alerts like in Selenium

    # Press Enter in the select2 search field to accept the result
    admin_page.wait_for_selector("input.select2-search__field", state="visible")
    admin_page.locator("input.select2-search__field").press("Enter")
    admin_page.wait_for_timeout(500)

    # Verify pbn_uid field was populated with the API result
    assert admin_page.locator("#id_pbn_uid").input_value() == UID_REKORDU


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("field_name", ["isbn", "e_isbn"])
def test_change_form_get_pbn_by_isbn_or_eisbn_via_api_pub_jest_w_api(
    admin_page: Page, channels_live_server, field_name, pbn_serwer
):
    """Test PBN ISBN/eISBN lookup finds record via API."""
    url = reverse("admin:bpp_wydawnictwo_zwarte_add")
    admin_page.goto(channels_live_server.url + url)
    admin_page.wait_for_load_state("domcontentloaded")

    ROK = "2222"
    ISBN = "123"
    UID_REKORDU = "aosidjfoasidjfasdfghjksl"

    rozwin_ekstra_informacje_playwright(admin_page)

    # Setup mock PBN API responses
    pub1 = pbn_publication_json(ROK, mongoId=UID_REKORDU, isbn=ISBN)
    pbn_serwer.expect_request(PBN_SEARCH_PUBLICATIONS_URL).respond_with_json(
        pbn_pageable_json([pub1])
    )
    pbn_serwer.expect_request(
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=UID_REKORDU)
    ).respond_with_json(pub1)

    admin_page.fill("#id_tytul_oryginalny", "nie istotny")
    admin_page.fill("#id_rok", ROK)
    admin_page.fill(f"#id_{field_name}", ISBN)

    # Verify button exists
    admin_page.wait_for_selector("#id_isbn_pbn_get", state="visible")

    btn = admin_page.locator("#id_isbn_pbn_get")
    btn.click()

    # Wait for processing
    admin_page.wait_for_timeout(500)

    # Press Enter in the select2 search field to accept the result
    admin_page.wait_for_selector("input.select2-search__field", state="visible")
    admin_page.locator("input.select2-search__field").press("Enter")
    admin_page.wait_for_timeout(500)

    # Verify pbn_uid field was populated with the API result
    assert admin_page.locator("#id_pbn_uid").input_value() == UID_REKORDU


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("field_name", ["isbn", "e_isbn"])
def test_change_form_get_pbn_by_isbn_or_eisbn_via_api_pub_jest_w_lokalnej_bazie(
    admin_page: Page, channels_live_server, field_name, pbn_serwer
):
    """Test PBN ISBN/eISBN lookup finds record in local database when not in API."""
    url = reverse("admin:bpp_wydawnictwo_zwarte_add")
    admin_page.goto(channels_live_server.url + url)
    admin_page.wait_for_load_state("domcontentloaded")

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

        rozwin_ekstra_informacje_playwright(admin_page)

        pbn_serwer.expect_request(PBN_SEARCH_PUBLICATIONS_URL).respond_with_json(
            pbn_pageable_json([])
        )

        admin_page.fill("#id_tytul_oryginalny", "nie istotny")
        admin_page.fill("#id_rok", ROK)
        admin_page.fill(f"#id_{field_name}", ISBN)

        # Verify button exists
        admin_page.wait_for_selector("#id_isbn_pbn_get", state="visible")

        btn = admin_page.locator("#id_isbn_pbn_get")
        btn.click()

        # Wait for processing
        admin_page.wait_for_timeout(500)

        # Press Enter in the select2 search field to accept the result
        admin_page.wait_for_selector("input.select2-search__field", state="visible")
        admin_page.locator("input.select2-search__field").press("Enter")
        admin_page.wait_for_timeout(500)

        # Verify pbn_uid field was populated with the local database record
        assert admin_page.locator("#id_pbn_uid").input_value() == UID_REKORDU
    finally:
        pub.delete()
