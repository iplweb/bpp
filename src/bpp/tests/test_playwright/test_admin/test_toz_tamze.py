import pytest
from django.urls import reverse
from playwright.sync_api import Page, expect

from bpp.models import Wydawnictwo_Ciagle
from bpp.models.patent import Patent
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.tests import any_ciagle
from bpp.tests.util import any_patent, any_zwarte


@pytest.mark.django_db(transaction=True)
def test_admin_wydawnictwo_zwarte_tamze(
    live_server, admin_page: Page, wydawca
):
    """Test the 'tamze' (ibidem) button for wydawnictwo_zwarte.

    The 'tamze' button creates a new publication form pre-populated with
    selected fields from the original publication.
    """
    c = any_zwarte(
        informacje="TO INFORMACJE",
        uwagi="te uwagi",
        miejsce_i_rok="te miejsce i rok",
        wydawca=wydawca,
        wydawca_opis="te wydawnictwo",
        www="ten adres WWW",
        isbn="Z_ISBN",
        e_isbn="E_ISBN",
    )

    admin_page.goto(
        live_server.url
        + reverse("admin:bpp_wydawnictwo_zwarte_change", args=(c.pk,))
    )
    admin_page.wait_for_load_state("domcontentloaded")

    # Click the "tamze" button
    admin_page.click("#tamze")

    # Wait for the add form to load
    admin_page.wait_for_selector("text=Dodaj wydawnictwo", timeout=10000)

    page_content = admin_page.content()

    # Verify fields that should be copied
    for elem in [
        "TO INFORMACJE",
        "te uwagi",
        "te miejsce i rok",
        "te wydawnictwo",
        "Z_ISBN",
        "E_ISBN",
        "Wydawca Testowy",
    ]:
        assert elem in page_content, f"BRAK {elem!r}"

    # Verify that www was NOT copied
    assert "ten adres WWW" not in page_content


@pytest.mark.django_db(transaction=True)
def test_admin_patent_tamze(live_server, admin_page: Page):
    """Test the 'tamze' (ibidem) button for patent.

    The 'tamze' button creates a new patent form pre-populated with
    selected fields from the original patent.
    """
    c = any_patent(informacje="TO INFORMACJE")

    admin_page.goto(
        live_server.url + reverse("admin:bpp_patent_change", args=(c.pk,))
    )
    admin_page.wait_for_load_state("domcontentloaded")

    # Click the "tamze" button
    admin_page.click("#tamze")

    # Wait for the add form to load
    admin_page.wait_for_load_state("domcontentloaded")

    # Verify that informacje field was copied
    informacje_input = admin_page.locator("#id_informacje")
    assert informacje_input.input_value() == "TO INFORMACJE"


@pytest.mark.django_db(transaction=True)
def test_admin_wydawnictwo_zwarte_toz(live_server, admin_page: Page):
    """Test the 'toz' (też oznacz) button for wydawnictwo_zwarte.

    The 'toz' button creates a copy of the publication record.
    """
    c = any_zwarte(informacje="TO INFOMRACJE")

    admin_page.goto(
        live_server.url
        + reverse("admin:bpp_wydawnictwo_zwarte_change", args=(c.pk,))
    )
    admin_page.wait_for_load_state("domcontentloaded")

    wcc = Wydawnictwo_Zwarte.objects.count
    assert wcc() == 1

    # Set up dialog handler to accept the confirmation dialog
    dialog_text = []

    def handle_dialog(dialog):
        dialog_text.append(dialog.message)
        dialog.accept()

    admin_page.on("dialog", handle_dialog)

    # Click the "toz" button
    admin_page.click("#toz")

    # Wait for the copy to be created
    admin_page.wait_for_function(
        f"() => true",  # Just wait for dialog to be processed
        timeout=5000,
    )

    # Verify the dialog contained the expected text
    assert any(
        "Utworzysz kopię tego rekordu" in text for text in dialog_text
    ), f"Expected dialog with 'Utworzysz kopię tego rekordu', got: {dialog_text}"

    # Wait for the new record to be created
    admin_page.wait_for_timeout(2000)
    assert wcc() == 2, f"Expected 2 records, got {wcc()}"


@pytest.mark.django_db(transaction=True)
def test_admin_wydawnictwo_ciagle_toz(live_server, admin_page: Page):
    """Test the 'toz' (też oznacz) button for wydawnictwo_ciagle.

    The 'toz' button creates a copy of the publication record.
    """
    Wydawnictwo_Ciagle.objects.all().delete()
    c = any_ciagle(informacje="TO INFORMACJE")

    admin_page.goto(
        live_server.url
        + reverse("admin:bpp_wydawnictwo_ciagle_change", args=(c.pk,))
    )
    admin_page.wait_for_load_state("domcontentloaded")

    wcc = Wydawnictwo_Ciagle.objects.count
    assert wcc() == 1

    # Set up dialog handler to accept the confirmation dialog
    dialog_text = []

    def handle_dialog(dialog):
        dialog_text.append(dialog.message)
        dialog.accept()

    admin_page.on("dialog", handle_dialog)

    # Click the "toz" button
    admin_page.click("#toz")

    # Wait for the copy to be created
    admin_page.wait_for_function(
        f"() => true",  # Just wait for dialog to be processed
        timeout=5000,
    )

    # Verify the dialog contained the expected text
    assert any(
        "Utworzysz kopię tego rekordu" in text for text in dialog_text
    ), f"Expected dialog with 'Utworzysz kopię tego rekordu', got: {dialog_text}"

    # Wait for the new record to be created
    admin_page.wait_for_timeout(2000)
    assert wcc() == 2, f"Expected 2 Wydawnictwo_Ciagle records, got {wcc()}"


@pytest.mark.django_db(transaction=True)
def test_admin_patent_toz(live_server, admin_page: Page):
    """Test the 'toz' (też oznacz) button for patent.

    The 'toz' button creates a copy of the patent record.
    """
    c = any_patent(informacje="TO INFORMACJE")

    admin_page.goto(
        live_server.url + reverse("admin:bpp_patent_change", args=(c.pk,))
    )
    admin_page.wait_for_load_state("domcontentloaded")

    wcc = Patent.objects.count
    assert wcc() == 1

    # Set up dialog handler to accept the confirmation dialog
    dialog_text = []

    def handle_dialog(dialog):
        dialog_text.append(dialog.message)
        dialog.accept()

    admin_page.on("dialog", handle_dialog)

    # Click the "toz" button
    admin_page.click("#toz")

    # Wait for the copy to be created
    admin_page.wait_for_function(
        f"() => true",  # Just wait for dialog to be processed
        timeout=5000,
    )

    # Verify the dialog contained the expected text
    assert any(
        "Utworzysz kopię tego rekordu" in text for text in dialog_text
    ), f"Expected dialog with 'Utworzysz kopię tego rekordu', got: {dialog_text}"

    # Wait for the navigation to complete
    admin_page.wait_for_selector("#navigation-menu", timeout=10000)

    # Wait for the new record to be created
    admin_page.wait_for_timeout(2000)
    assert wcc() == 2, f"Expected 2 Patent records, got {wcc()}"


@pytest.mark.django_db(transaction=True)
def test_admin_wydawnictwo_ciagle_tamze(live_server, admin_page: Page):
    """Test the 'tamze' (ibidem) button for wydawnictwo_ciagle.

    The 'tamze' button creates a new publication form pre-populated with
    selected fields from the original publication.
    """
    c = any_ciagle(informacje="TO INFORMACJE", uwagi="te uwagi", www="te www")

    admin_page.goto(
        live_server.url
        + reverse("admin:bpp_wydawnictwo_ciagle_change", args=(c.pk,))
    )
    admin_page.wait_for_load_state("domcontentloaded")

    # Click the "tamze" button
    admin_page.click("#tamze")

    # Wait for the add form to load
    admin_page.wait_for_selector("text=Dodaj wydawnictwo", timeout=10000)

    page_content = admin_page.content()

    # Verify fields that should be copied
    for elem in ["TO INFORMACJE", "te uwagi"]:
        assert elem in page_content, f"BRAK {elem!r}"

    # Verify that www was NOT copied
    assert "te www" not in page_content
