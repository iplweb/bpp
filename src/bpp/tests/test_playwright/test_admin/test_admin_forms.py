import pytest
from django.db import transaction
from django.urls import reverse
from playwright.sync_api import Page

from bpp.models.zrodlo import Punktacja_Zrodla
from bpp.tests import any_autor, any_jednostka
from bpp.tests.util import CURRENT_YEAR, any_zrodlo
from django_bpp.playwright_util import select_select2_autocomplete


@pytest.mark.django_db(transaction=True)
def test_automatycznie_uzupelnij_punkty(admin_page: Page, channels_live_server):
    """Test automatic points population button without selecting source first."""
    url = reverse("admin:bpp_wydawnictwo_ciagle_add")

    admin_page.goto(channels_live_server.url + url)

    any_zrodlo(nazwa="FOO BAR")

    # Wait for the button to appear
    admin_page.wait_for_selector("#id_wypelnij_pola_punktacji_button", state="visible")

    # Setup dialog handler to capture first message
    dialog_messages = []

    def handle_dialog(dialog):
        dialog_messages.append(dialog.message)
        dialog.accept()

    admin_page.on("dialog", handle_dialog)

    # Click button without selecting source
    admin_page.click("#id_wypelnij_pola_punktacji_button")

    # Wait for dialog to be handled
    admin_page.wait_for_timeout(1000)
    assert len(dialog_messages) > 0
    assert "Najpierw wybierz jakie" in dialog_messages[0]

    # Select source using select2 autocomplete
    select_select2_autocomplete(
        admin_page, "id_zrodlo", "FOO", wait_for_new_value=True, timeout=30000
    )

    # Wait for select2 to fully update
    admin_page.wait_for_timeout(1000)

    # Click button again
    admin_page.click("#id_wypelnij_pola_punktacji_button")

    # Wait for second dialog
    admin_page.wait_for_timeout(1000)
    assert len(dialog_messages) > 1
    assert "Uzupełnij pole" in dialog_messages[1]

    # Disable onbeforeunload handler
    admin_page.evaluate("window.onbeforeunload = function(e) {};")


@pytest.mark.django_db(transaction=True)
def test_liczba_znakow_wydawniczych_liczba_arkuszy_wydawniczych(
    admin_page: Page, channels_live_server
):
    """Test automatic calculation between character count and sheet count."""
    url = reverse("admin:bpp_wydawnictwo_zwarte_add")
    admin_page.goto(channels_live_server.url + url)

    # Wait for liczba_arkuszy_wydawniczych field to be present
    admin_page.wait_for_selector(
        "#id_liczba_arkuszy_wydawniczych", state="attached", timeout=10000
    )

    # Set liczba_znakow_wydawniczych to 40000 and verify automatic calculation
    admin_page.evaluate(
        "django.jQuery('#id_liczba_znakow_wydawniczych').val('40000').change()"
    )
    assert admin_page.locator("#id_liczba_arkuszy_wydawniczych").input_value() == "1.00"

    # Set liczba_arkuszy_wydawniczych to 0.5 and verify automatic calculation
    admin_page.evaluate(
        "django.jQuery('#id_liczba_arkuszy_wydawniczych').val('0.5').change()"
    )
    assert admin_page.locator("#id_liczba_znakow_wydawniczych").input_value() == "20000"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("url", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_uzupelnij_strona_tom_nr_zeszytu(url, admin_page: Page, channels_live_server):
    """Test automatic population of page, volume, and issue number fields."""
    url_path = reverse(f"admin:bpp_{url}_add")
    admin_page.goto(channels_live_server.url + url_path)
    admin_page.wait_for_load_state("domcontentloaded")

    # Wait for form fields to be present
    admin_page.wait_for_selector('textarea[name="informacje"]', state="attached")
    admin_page.wait_for_selector("#id_strony_get", state="attached")

    # Fill in the informacje and szczegoly fields
    # informacje is TextField (textarea), szczegoly is CharField (input)
    admin_page.fill('textarea[name="informacje"]', "1993 vol. 5 z. 1")
    admin_page.fill('input[name="szczegoly"]', "s. 4-3")

    # Scroll element into view and click
    admin_page.evaluate(
        """
        const elem = document.getElementById('id_strony_get');
        elem.scrollIntoView();
    """
    )
    admin_page.click("#id_strony_get")

    # Wait for tom field to be populated
    admin_page.wait_for_function(
        """() => {
            const tom = document.querySelector('input[name="tom"]');
            return tom && tom.value !== '';
        }"""
    )

    # Verify extracted values
    assert admin_page.locator('input[name="strony"]').input_value() == "4-3"
    assert admin_page.locator('input[name="tom"]').input_value() == "5"

    if url == "wydawnictwo_ciagle":
        assert admin_page.locator('input[name="nr_zeszytu"]').input_value() == "1"


@pytest.mark.django_db(transaction=True)
def test_admin_wydawnictwo_ciagle_dowolnie_zapisane_nazwisko(
    admin_page: Page, channels_live_server, autor_jan_kowalski
):
    """Test entering a custom author name in the zapisany_jako field."""
    admin_page.goto(
        channels_live_server.url + reverse("admin:bpp_wydawnictwo_ciagle_add")
    )
    admin_page.wait_for_load_state("domcontentloaded")

    # Click the "add author" button (grp-add-handler)
    admin_page.locator(".grp-add-handler").first.click()

    # Wait for the autor field to appear
    admin_page.wait_for_selector("#id_autorzy_set-0-autor", state="visible")

    # Select "Kowalski Jan" in the autor field using select2
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-0-autor", "Kowalski Jan", timeout=30000
    )

    # Enter "Dowolny tekst" in the zapisany_jako field using select2
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-0-zapisany_jako", "Dowolny tekst", timeout=30000
    )

    # Verify the value was set correctly
    assert (
        admin_page.locator("#id_autorzy_set-0-zapisany_jako").input_value()
        == "Dowolny tekst"
    )


@pytest.mark.django_db(transaction=True)
def test_upload_punkty(admin_page: Page, channels_live_server):
    """Test uploading points to source scoring data."""
    any_zrodlo(nazwa="WTF LOL")

    url = reverse("admin:bpp_wydawnictwo_ciagle_add")
    admin_page.goto(channels_live_server.url + url)

    select_select2_autocomplete(admin_page, "id_zrodlo", "WTF", timeout=30000)

    rok = admin_page.locator("#id_rok")
    rok.scroll_into_view_if_needed()
    admin_page.fill("#id_rok", str(CURRENT_YEAR))

    impact_factor = admin_page.locator("#id_impact_factor")
    impact_factor.scroll_into_view_if_needed()
    admin_page.fill("#id_impact_factor", "1")

    elem = admin_page.locator("#id_dodaj_punktacje_do_zrodla_button")
    elem.scroll_into_view_if_needed()
    elem.click()

    # Wait for Punktacja_Zrodla to be created
    admin_page.wait_for_function(
        "() => { return true; }",  # Dummy wait, actual check below
        timeout=5000,
    )
    admin_page.wait_for_timeout(1000)
    assert Punktacja_Zrodla.objects.count() == 1
    assert Punktacja_Zrodla.objects.all()[0].impact_factor == 1

    admin_page.fill("#id_impact_factor", "2")

    # Setup dialog handler for the alert
    dialog_messages = []

    def handle_dialog(dialog):
        dialog_messages.append(dialog.message)
        dialog.accept()

    admin_page.on("dialog", handle_dialog)

    admin_page.click("#id_dodaj_punktacje_do_zrodla_button")

    # Wait for dialog to appear
    admin_page.wait_for_timeout(1000)
    assert len(dialog_messages) > 0
    assert "Punktacja dla tego roku już istnieje" in dialog_messages[0]

    # Wait for the punktacja to be updated
    admin_page.wait_for_timeout(1000)
    assert Punktacja_Zrodla.objects.all()[0].impact_factor == 2

    admin_page.evaluate("window.onbeforeunload = function(e) {};")


@pytest.mark.django_db(transaction=True)
def test_admin_uzupelnij_punkty(admin_page: Page, channels_live_server):
    """Test automatic points population from source scoring data."""
    from bpp.tests.util import any_ciagle, any_zrodlo

    z = any_zrodlo(nazwa="WTF LOL")

    kw = dict(zrodlo=z)
    f = Punktacja_Zrodla.objects.create
    f(impact_factor=10.1, punkty_kbn=10.2, rok=CURRENT_YEAR, **kw)
    f(impact_factor=11.1, punkty_kbn=11.2, rok=CURRENT_YEAR + 1, **kw)

    c = any_ciagle(zrodlo=z, impact_factor=5, punkty_kbn=5)

    url = reverse("admin:bpp_wydawnictwo_ciagle_change", args=(c.pk,))
    admin_page.goto(channels_live_server.url + url)
    admin_page.wait_for_load_state("domcontentloaded")

    # Wait for fields to be visible
    admin_page.wait_for_selector("#id_rok", state="visible")
    admin_page.wait_for_selector("#id_punkty_kbn", state="visible")

    # Verify initial values
    assert admin_page.locator("#id_rok").input_value() == str(CURRENT_YEAR)
    assert admin_page.locator("#id_punkty_kbn").input_value() == "5.00"

    # Click button to auto-fill points
    button = admin_page.locator("#id_wypelnij_pola_punktacji_button")
    button.click()

    # Wait for punkty_kbn to be updated (this proves the AJAX call completed)
    admin_page.wait_for_function(
        "() => document.getElementById('id_punkty_kbn').value === '10.20'",
        timeout=10000,
    )

    # Now verify the button text changed to "Wypełniona!"
    # Note: The button may not always update immediately, so we use a longer timeout
    admin_page.wait_for_function(
        "() => document.getElementById('id_wypelnij_pola_punktacji_button').value === 'Wypełniona!'",
        timeout=15000,
    )

    # Trigger change event on rok field
    admin_page.evaluate("django.jQuery('#id_rok').trigger('change')")

    # Wait for button to reset
    admin_page.wait_for_function(
        "() => document.getElementById('id_wypelnij_pola_punktacji_button').value === 'Wypełnij pola punktacji'",
        timeout=10000,
    )

    # Change year to CURRENT_YEAR + 1
    admin_page.fill("#id_rok", str(CURRENT_YEAR + 1))

    # Click button again
    button.click()

    # Wait for punkty_kbn to update to 11.20
    admin_page.wait_for_function(
        "() => document.getElementById('id_punkty_kbn').value === '11.20'",
        timeout=10000,
    )

    # Verify button shows "Wypełniona!"
    assert button.input_value() == "Wypełniona!"

    # Clear zrodlo selection
    admin_page.evaluate(
        """
        django.jQuery('#id_zrodlo').val(null).trigger('change');
    """
    )

    # Wait for button to reset
    admin_page.wait_for_function(
        "() => document.getElementById('id_wypelnij_pola_punktacji_button').value === 'Wypełnij pola punktacji'",
        timeout=10000,
    )

    admin_page.evaluate("window.onbeforeunload = function(e) {};")


@pytest.fixture
def autorform_jednostka(db):
    """Create an author with a unit for autorform tests."""
    with transaction.atomic():
        a = any_autor(nazwisko="KOWALSKI", imiona="Jan Sebastian")
        j = any_jednostka(nazwa="WTF LOL")
        j.dodaj_autora(a)
    return j


@pytest.mark.django_db(transaction=True)
def test_autorform_uzupelnianie_jednostki(
    admin_page: Page, channels_live_server, autorform_jednostka
):
    """Test automatic unit population when selecting an author."""
    url = reverse("admin:bpp_wydawnictwo_ciagle_add")
    admin_page.goto(channels_live_server.url + url)
    admin_page.wait_for_load_state("domcontentloaded")

    # Disable onbeforeunload handler early
    admin_page.evaluate("window.onbeforeunload = function(e) {};")

    # Click the "add author" button (grp-add-handler)
    admin_page.locator(".grp-add-handler").first.click()

    # Wait for the autor field to appear
    admin_page.wait_for_selector("#id_autorzy_set-0-autor", state="visible")

    # Select "KOWALSKI" in the autor field using select2
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-0-autor", "KOWALSKI", timeout=30000
    )

    # Wait for jednostka field to be auto-populated
    admin_page.wait_for_function(
        f"() => document.getElementById('id_autorzy_set-0-jednostka').value === "
        f"'{autorform_jednostka.pk}'",
        timeout=10000,
    )


@pytest.mark.django_db(transaction=True)
def test_autorform_kasowanie_autora(
    admin_page: Page, channels_live_server, autorform_jednostka
):
    """Test that clearing author also clears unit selection."""
    url = reverse("admin:bpp_wydawnictwo_ciagle_add")
    admin_page.goto(channels_live_server.url + url)
    admin_page.wait_for_load_state("domcontentloaded")

    # Disable onbeforeunload handler early
    admin_page.evaluate("window.onbeforeunload = function(e) {};")

    # Click the "add author" button (grp-add-handler)
    admin_page.locator(".grp-add-handler").first.click()

    # Wait for the autor field to appear
    admin_page.wait_for_selector("#id_autorzy_set-0-autor", state="visible")

    # Select "KOW" (shortcut for KOWALSKI) in the autor field using select2
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-0-autor", "KOW", timeout=30000
    )

    # Wait for jednostka field to be auto-populated
    admin_page.wait_for_function(
        f"() => document.getElementById('id_autorzy_set-0-jednostka').value === "
        f"'{autorform_jednostka.pk}'",
        timeout=10000,
    )

    # Clear the autor selection using select2 clear
    admin_page.evaluate(
        "django.jQuery('#id_autorzy_set-0-autor').val(null).trigger('change');"
    )

    # Wait for jednostka field to be cleared (value should contain newline or be empty)
    admin_page.wait_for_function(
        """() => {
            const jed = document.getElementById('id_autorzy_set-0-jednostka');
            return jed.value === '' || jed.value.indexOf('\\n') !== -1;
        }""",
        timeout=10000,
    )
