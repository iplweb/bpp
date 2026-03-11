"""Playwright tests for importer_publikacji step 4 (authors).

Tests the author matching modal: opening, editing disciplines,
and verifying that only a single modal opens (not two).
"""

import pytest
from django.test import Client
from django.urls import reverse
from model_bakery import baker
from playwright.sync_api import Page, expect


@pytest.fixture
def importer_page(
    page: Page,
    wprowadzanie_danych_user,
    transactional_db,
):
    """Playwright page authenticated as user with import permissions."""
    client = Client()
    client.force_login(wprowadzanie_danych_user)
    session_cookie = client.cookies["sessionid"]
    page.context.add_cookies(
        [
            {
                "name": "sessionid",
                "value": session_cookie.value,
                "domain": "localhost",
                "path": "/",
            }
        ]
    )
    return page


@pytest.fixture
def zrodlo_blood(db):
    """Journal 'Blood' — target for DOI 10.1182/blood-2025-848."""
    from bpp.models import Zrodlo

    return baker.make(Zrodlo, nazwa="Blood", issn="0006-4971")


@pytest.mark.vcr(
    match_on=("method", "scheme", "path", "query"),
    ignore_localhost=True,
)
def test_import_crossref_doi_author_modal_single_open(
    importer_page: Page,
    live_server,
    uczelnia,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    zrodlo_blood,
):
    """Import DOI from CrossRef, navigate to step 4, and verify
    that clicking a row opens exactly ONE modal (not two)."""
    page = importer_page
    url = live_server.url + reverse("importer_publikacji:index")
    page.goto(url)
    page.wait_for_load_state("networkidle")

    # Dismiss cookie consent banner
    page.evaluate("Cookielaw.accept();")

    # Step 1: Enter DOI and fetch
    page.locator('input[name="provider"][value="CrossRef"]').check()
    page.fill('input[name="identifier"]', "10.1182/blood-2025-848")
    page.locator('#input-identifier button[type="submit"]').click()

    # Wait for step 2 (verify) to appear
    page.wait_for_selector("text=Krok 2", timeout=30000)

    # Step 2: Select charakter_formalny, typ_kbn, jezyk
    # and submit
    page.select_option(
        'select[name="charakter_formalny"]',
        label=page.locator('select[name="charakter_formalny"] option')
        .nth(1)
        .text_content(),
    )
    page.select_option(
        'select[name="typ_kbn"]',
        label=page.locator('select[name="typ_kbn"] option').nth(1).text_content(),
    )
    # jezyk may be auto-filled; ensure it's set
    jezyk_select = page.locator('select[name="jezyk"]')
    if not jezyk_select.input_value():
        page.select_option(
            'select[name="jezyk"]',
            label=page.locator('select[name="jezyk"] option').nth(1).text_content(),
        )

    page.locator('button[type="submit"]:has-text("Dalej")').click()

    # Wait for step 3 (source) to appear
    page.wait_for_selector("text=Krok 3", timeout=30000)

    # Step 3: Source matching - for journal articles
    # the zrodlo field needs a value. Since we don't have
    # a matching Zrodlo in DB, we need to handle the form.
    # If there's already a zrodlo select, pick one or
    # create one via the form.
    zrodlo_select = page.locator('select[name="zrodlo"]')
    if zrodlo_select.count():
        # The source field is rendered as a select2 or
        # regular select. Check if any option exists.
        options = page.locator('select[name="zrodlo"] option')
        if options.count() > 1:
            page.select_option(
                'select[name="zrodlo"]',
                label=options.nth(1).text_content(),
            )

    page.locator('button[type="submit"]:has-text("Dalej")').click()

    # Wait for step 4 (authors) to appear
    page.wait_for_selector("text=Krok 4", timeout=30000)

    # Verify authors table is present
    expect(page.locator("#authors-table")).to_be_visible()

    # Count how many author rows exist
    rows = page.locator("tr.author-row-clickable")
    row_count = rows.count()
    assert row_count > 0, "Expected at least one author row"

    # Click on the first author row to open the modal
    rows.first.click()

    # Wait for the modal to appear
    modal = page.locator("#author-edit-modal")
    expect(modal).to_be_visible(timeout=5000)

    # Verify only ONE modal overlay is visible
    # Foundation Reveal creates .reveal-overlay elements
    overlays = page.locator(".reveal-overlay:visible")
    assert overlays.count() == 1, f"Expected 1 modal overlay, got {overlays.count()}"

    # Verify modal title is populated (not empty)
    modal_title = page.locator("#modal-author-title")
    expect(modal_title).not_to_be_empty()
    title_text = modal_title.text_content()
    assert title_text.startswith("Edycja:"), (
        f"Expected modal title starting with 'Edycja:', got '{title_text}'"
    )

    # Verify discipline select is present
    expect(page.locator("#modal-dyscyplina-select")).to_be_visible()

    # Close modal
    page.locator('#author-edit-modal button:has-text("Anuluj")').click()
    expect(modal).not_to_be_visible(timeout=5000)

    # Test opening via "Edytuj" button
    edit_btn = rows.first.locator(".btn-edit-author")
    edit_btn.click()

    expect(modal).to_be_visible(timeout=5000)

    # Again verify only ONE overlay
    overlays = page.locator(".reveal-overlay:visible")
    assert overlays.count() == 1, (
        f"Expected 1 modal overlay after Edytuj click, got {overlays.count()}"
    )

    # Close modal
    page.locator('#author-edit-modal button:has-text("Anuluj")').click()
    expect(modal).not_to_be_visible(timeout=5000)
