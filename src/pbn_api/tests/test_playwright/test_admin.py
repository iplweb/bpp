import pytest
from django.contrib.contenttypes.models import ContentType
from playwright.sync_api import Page

from pbn_api.models import SentData


@pytest.mark.django_db
def test_pbn_api_admin_SentDataAdmin_wyslij_ponownie(
    wydawnictwo_zwarte, admin_page: Page, channels_live_server
):
    s = SentData.objects.create(
        object_id=wydawnictwo_zwarte.pk,
        content_type=ContentType.objects.get_for_model(wydawnictwo_zwarte),
        data_sent={"foo": "bar"},
    )

    admin_page.goto(
        channels_live_server.url + f"/admin/pbn_api/sentdata/{s.pk}/change"
    )

    # Wait for the button to appear
    admin_page.wait_for_selector("#wyslij-ponownie", state="visible")

    # Click the button
    admin_page.click("#wyslij-ponownie")

    # Wait for page load and check for expected text
    admin_page.wait_for_load_state("domcontentloaded")

    # Wait for the text to appear in page content (with timeout)
    admin_page.wait_for_function(
        "() => document.body.textContent.includes('nie będzie eksportowany')",
        timeout=30000,
    )

    assert "nie będzie eksportowany" in admin_page.content()
