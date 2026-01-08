"""Playwright tests for Clarivate/WOS integration in admin forms."""

from unittest.mock import Mock

import pytest
from django.urls import reverse
from playwright.sync_api import Page

pytestmark = [pytest.mark.slow, pytest.mark.playwright]


@pytest.fixture(scope="function")
def page_z_wydawnictwem(admin_page: Page, live_server, wydawnictwo_ciagle):
    """Set up admin page with an existing wydawnictwo_ciagle record."""
    admin_page.goto(
        live_server.url
        + reverse("admin:bpp_wydawnictwo_ciagle_change", args=(wydawnictwo_ciagle.pk,))
    )
    admin_page.wait_for_load_state("domcontentloaded")
    # Disable onbeforeunload handler early
    admin_page.evaluate("window.onbeforeunload = function(e) {};")
    return admin_page


@pytest.mark.django_db(transaction=True)
def test_admin_get_wos_information_clarivate_brak_danych(page_z_wydawnictwem, denorms):
    """Test WOS button shows error when DOI is missing."""
    page = page_z_wydawnictwem

    # Setup dialog handler to capture alert message
    dialog_messages = []

    def handle_dialog(dialog):
        dialog_messages.append(dialog.message)
        dialog.accept()

    page.on("dialog", handle_dialog)

    # Scroll to and click the button
    elem = page.locator("#id_liczba_cytowan_get")
    elem.scroll_into_view_if_needed()
    elem.click()

    # Wait for dialog
    page.wait_for_timeout(1000)

    # Verify the dialog mentions DOI
    assert len(dialog_messages) > 0
    assert "DOI" in dialog_messages[0]


@pytest.mark.django_db(transaction=True)
def test_admin_get_wos_information_clarivate_pmid(
    uczelnia, mocker, page_z_wydawnictwem
):
    """Test successful retrieval of citation count from WOS using PMID."""
    m = Mock()
    m.query_single = Mock(return_value={"timesCited": "31337"})
    mocker.patch("bpp.models.struktura.Uczelnia.wosclient", return_value=m)

    page = page_z_wydawnictwem

    # Fill in the pubmed_id field
    page.fill("#id_pubmed_id", "31337")

    # Scroll to and click the button
    elem = page.locator("#id_liczba_cytowan_get")
    elem.scroll_into_view_if_needed()
    elem.click()

    # Wait for button to show "Pobrano!"
    page.wait_for_function(
        "() => document.getElementById('id_liczba_cytowan_get').value === 'Pobrano!'",
        timeout=15000,
    )

    # Verify the citation count was populated
    assert page.locator("#id_liczba_cytowan_get").input_value() == "Pobrano!"
    assert page.locator("#id_liczba_cytowan").input_value() == "31337"


@pytest.mark.django_db(transaction=True)
def test_admin_get_wos_information_clarivate_err(uczelnia, page_z_wydawnictwem, mocker):
    """Test error handling when WOS client raises an exception."""
    m = Mock()
    m.query_single = Mock(side_effect=Exception("lel"))
    mocker.patch("bpp.models.struktura.Uczelnia.wosclient", return_value=m)

    page = page_z_wydawnictwem

    # Setup dialog handler to capture alert message
    dialog_messages = []

    def handle_dialog(dialog):
        dialog_messages.append(dialog.message)
        dialog.accept()

    page.on("dialog", handle_dialog)

    # Fill in the pubmed_id field
    page.fill("#id_pubmed_id", "31337")

    # Scroll to and click the button
    elem = page.locator("#id_liczba_cytowan_get")
    elem.scroll_into_view_if_needed()
    elem.click()

    # Wait for dialog
    page.wait_for_timeout(1000)

    # Verify the dialog shows internal error message
    assert len(dialog_messages) > 0
    assert "Wewnętrzny błąd systemu" in dialog_messages[0]


@pytest.mark.django_db(transaction=True)
def test_admin_get_wos_information_clarivate_misconfigured(
    uczelnia, page_z_wydawnictwem, mocker
):
    """Test error messages when Clarivate credentials are not configured."""
    uczelnia.clarivate_password = uczelnia.clarivate_username = ""
    uczelnia.save()

    page = page_z_wydawnictwem

    # Setup dialog handler to capture alert messages
    dialog_messages = []

    def handle_dialog(dialog):
        dialog_messages.append(dialog.message)
        dialog.accept()

    page.on("dialog", handle_dialog)

    # Fill in the pubmed_id field
    page.fill("#id_pubmed_id", "31337")

    # Scroll to and click the button
    elem = page.locator("#id_liczba_cytowan_get")
    elem.scroll_into_view_if_needed()
    elem.click()

    # Wait for dialog about missing username
    page.wait_for_timeout(1000)
    assert len(dialog_messages) > 0
    assert "Brak użytkownika API" in dialog_messages[0]

    # Now set username but no password
    uczelnia.clarivate_username = "fa"
    uczelnia.save()

    # Click button again
    elem.click()

    # Wait for dialog about missing password
    page.wait_for_timeout(1000)
    assert len(dialog_messages) > 1
    assert "Brak hasła do API" in dialog_messages[1]
