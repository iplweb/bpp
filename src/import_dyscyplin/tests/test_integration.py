import os

import pytest
from django.urls import reverse
from model_bakery import baker
from playwright.sync_api import Page

from bpp.models import Uczelnia

from django_bpp.playwright_util import proper_click_element, wait_for_page_load


@pytest.mark.django_db(transaction=True)
def test_integracyjny(admin_page: Page, channels_live_server, settings):
    settings.CELERY_ALWAYS_EAGER = True
    settings.CELERY_EAGER_PROPAGATES_EXCEPTIONS = True

    # Create Uczelnia and store reference for cleanup
    uczelnia = baker.make(Uczelnia)
    try:
        admin_page.goto(channels_live_server.url + reverse("import_dyscyplin:index"))

        # Accept cookies
        admin_page.evaluate("Cookielaw.accept()")
        wait_for_page_load(admin_page)

        # Click add new file button
        admin_page.click("#add-new-file")

        # Upload file
        file_path = os.path.join(
            os.path.dirname(__file__), "../static/import_dyscyplin/xlsx/default.xlsx"
        )
        admin_page.set_input_files("#id_plik", file_path)

        # Click submit button
        admin_page.click("#id_submit")
        wait_for_page_load(admin_page)

        # Check if there's a second submit button on the next page
        if admin_page.locator("#submit-id-submit").count() > 0:
            # Scroll submit button into view and click it
            submit_btn = admin_page.locator("#submit-id-submit")
            submit_btn.scroll_into_view_if_needed()
            proper_click_element(admin_page, "#submit-id-submit")
            wait_for_page_load(admin_page)

        # Wait for "Lubelski" to appear in the page content
        admin_page.wait_for_function(
            "() => document.body.textContent.includes('Lubelski')", timeout=5000
        )
    finally:
        # Clean up the created Uczelnia record
        if uczelnia:
            uczelnia.delete()
