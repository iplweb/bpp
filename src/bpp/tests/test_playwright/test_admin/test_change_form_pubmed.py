import pytest
from django.urls import reverse
from playwright.sync_api import Page

from bpp.views.api import const


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
    admin_page: Page, channels_live_server, url, tytul, wynik
):
    url = reverse(f"admin:bpp_{url}_add")
    admin_page.goto(channels_live_server.url + url)

    admin_page.fill("#id_tytul_oryginalny", tytul)

    # Check if button exists
    if admin_page.locator("#id_pubmed_id_get").count() == 0:
        raise Exception("Nie mozna znalexc elementu")

    # Set up dialog handler to capture message
    dialog_message = []

    def handle_dialog(dialog):
        dialog_message.append(dialog.message)
        dialog.accept()

    admin_page.once("dialog", handle_dialog)

    # Click the button
    admin_page.click("#id_pubmed_id_get")

    # Wait for dialog to be handled
    admin_page.wait_for_timeout(500)

    # Assert the dialog message contains the expected text
    assert len(dialog_message) > 0, "No dialog appeared"
    assert wynik in dialog_message[0], f"Expected '{wynik}' in '{dialog_message[0]}'"
