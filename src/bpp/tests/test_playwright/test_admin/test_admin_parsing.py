import pytest
from django.urls import reverse
from playwright.sync_api import Page

from bpp.const import CHARAKTER_OGOLNY_KSIAZKA
from bpp.models import Charakter_Formalny
from django_bpp.playwright_util import select_select2_autocomplete


@pytest.mark.django_db(transaction=True)
def test_admin_wydawnictwo_zwarte_uzupelnij_rok(
    wydawnictwo_zwarte, admin_page: Page, channels_live_server
):
    """
    Test year extraction from miejsce_i_rok field and parent publication.
    """
    admin_page.goto(
        channels_live_server.url + reverse("admin:bpp_wydawnictwo_zwarte_add")
    )
    admin_page.wait_for_load_state("domcontentloaded")

    # Verify rok field is initially empty
    rok = admin_page.locator("#id_rok")
    assert rok.input_value() == ""

    # Fill miejsce_i_rok with text containing a year
    admin_page.fill('input[name="miejsce_i_rok"]', "Lublin 2002")

    # Click the year extraction button
    admin_page.click("#id_rok_button")

    # Wait for the year field to be populated
    admin_page.wait_for_function(
        "() => document.querySelector('#id_rok').value === '2002'", timeout=5000
    )

    # Create Charakter_Formalny for the parent publication
    chf = Charakter_Formalny.objects.create(
        nazwa="charakter", skrot="ch", charakter_ogolny=CHARAKTER_OGOLNY_KSIAZKA
    )

    # Update wydawnictwo_zwarte to be a valid parent publication
    wydawnictwo_zwarte.rok = 1997
    wydawnictwo_zwarte.charakter_formalny = chf
    wydawnictwo_zwarte.save()

    # Select wydawnictwo_zwarte as parent publication (wydawnictwo_nadrzedne)
    select_select2_autocomplete(
        admin_page, "id_wydawnictwo_nadrzedne", "Wydawnictwo Zwarte"
    )

    # Clear rok and click button - should get year from miejsce_i_rok
    admin_page.fill("#id_rok", "")
    admin_page.click("#id_rok_button")
    admin_page.wait_for_function(
        "() => document.querySelector('#id_rok').value === '2002'", timeout=5000
    )

    # Clear miejsce_i_rok and click button - should get year from parent publication
    admin_page.fill('input[name="miejsce_i_rok"]', "")
    admin_page.click("#id_rok_button")
    admin_page.wait_for_function(
        "() => document.querySelector('#id_rok').value === '1997'", timeout=5000
    )


def test_admin_wydawnictwo_ciagle_uzupelnij_rok(admin_page: Page, channels_live_server):
    """
    Test year extraction from informacje field.
    """
    admin_page.goto(
        channels_live_server.url + reverse("admin:bpp_wydawnictwo_ciagle_add")
    )

    # Fill informacje field with text containing a year
    admin_page.fill('textarea[name="informacje"]', "Lublin 2002 test")

    # Click the year extraction button
    admin_page.click("#id_rok_button")

    # Wait for the year field to be populated
    admin_page.wait_for_function(
        "() => document.querySelector('#id_rok').value === '2002'", timeout=5000
    )

    assert admin_page.locator("#id_rok").input_value() == "2002"

    # Clear informacje and test with no data
    admin_page.fill('textarea[name="informacje"]', "")

    # Click the year button again
    admin_page.click("#id_rok_button")

    # Wait for button value to change to "Brak danych"
    admin_page.wait_for_function(
        "() => document.querySelector('#id_rok_button').value === 'Brak danych'",
        timeout=5000,
    )

    assert admin_page.locator("#id_rok_button").input_value() == "Brak danych"
