import os

import pytest
from django.urls import reverse
from playwright.sync_api import Page

from bpp.models import Autor_Dyscyplina, Autor_Jednostka
from django_bpp.playwright_util import select_select2_autocomplete


def wait_for_discipline_populated(page: Page, field_id: str, timeout: int = 10000):
    """Wait for discipline field to be populated via AJAX after author selection."""
    page.wait_for_function(
        f"() => document.querySelector('#{field_id}').value !== ''",
        timeout=timeout,
    )


@pytest.mark.django_db(transaction=True)
def test_zglos_publikacje_drugi_autor_dyscyplina(
    admin_page: Page,
    channels_live_server,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    dyscyplina1,
    rok,
):
    """Test discipline auto-population when adding 2nd author."""
    for autor in autor_jan_kowalski, autor_jan_nowak:
        Autor_Dyscyplina.objects.get_or_create(
            autor=autor, rok=rok, dyscyplina_naukowa=dyscyplina1
        )
        Autor_Jednostka.objects.get_or_create(autor=autor, jednostka=jednostka)

    admin_page.goto(
        channels_live_server.url + reverse("zglos_publikacje:nowe_zgloszenie")
    )
    admin_page.wait_for_load_state("domcontentloaded")
    admin_page.evaluate("if(window.Cookielaw) Cookielaw.accept()")

    admin_page.fill("[name='0-tytul_oryginalny']", "test")
    admin_page.select_option("[name='0-rodzaj_zglaszanej_publikacji']", "2")
    admin_page.fill("[name='0-strona_www']", "https://www.onet.pl/")
    admin_page.fill("[name='0-rok']", str(rok))
    admin_page.fill("[name='0-email']", "moj@email.pl")

    admin_page.click("#id-wizard-submit")
    admin_page.wait_for_load_state("domcontentloaded")

    n = 1
    admin_page.click("#add-form")
    admin_page.wait_for_selector(f"#id_2-{n}-autor", state="visible")
    select_select2_autocomplete(admin_page, f"id_2-{n}-autor", "Kowal", timeout=30000)

    # Wait for discipline to be auto-populated via AJAX
    wait_for_discipline_populated(admin_page, f"id_2-{n}-dyscyplina_naukowa")

    assert admin_page.locator(f"#id_2-{n}-dyscyplina_naukowa").input_value() == str(
        dyscyplina1.pk
    )


@pytest.mark.django_db(transaction=True)
def test_zglos_publikacje_z_plikiem_drugi_autor_dyscyplina(
    admin_page: Page,
    channels_live_server,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    dyscyplina1,
    rok,
):
    """Test discipline auto-population with file upload."""
    for autor in autor_jan_kowalski, autor_jan_nowak:
        Autor_Dyscyplina.objects.get_or_create(
            autor=autor, rok=rok, dyscyplina_naukowa=dyscyplina1
        )
        Autor_Jednostka.objects.get_or_create(autor=autor, jednostka=jednostka)

    admin_page.goto(
        channels_live_server.url + reverse("zglos_publikacje:nowe_zgloszenie")
    )
    admin_page.wait_for_load_state("domcontentloaded")
    admin_page.evaluate("if(window.Cookielaw) Cookielaw.accept()")

    admin_page.fill("[name='0-tytul_oryginalny']", "test")
    admin_page.select_option("[name='0-rodzaj_zglaszanej_publikacji']", "2")
    admin_page.fill("[name='0-rok']", str(rok))
    admin_page.fill("[name='0-email']", "moj@email.pl")

    admin_page.click("#id-wizard-submit")
    admin_page.wait_for_load_state("domcontentloaded")

    plik = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "example.pdf"))
    admin_page.set_input_files("[name='1-plik']", plik)

    admin_page.click("#id-wizard-submit")
    admin_page.wait_for_load_state("domcontentloaded")

    # Wait for author step to be ready with add-form button
    admin_page.wait_for_selector("#add-form", state="visible", timeout=10000)

    n = 1
    admin_page.click("#add-form")
    admin_page.wait_for_selector(f"#id_2-{n}-autor", state="attached", timeout=10000)

    # Scroll the form into view to ensure Select2 is visible
    admin_page.locator(f"#id_2-{n}-autor").scroll_into_view_if_needed()
    admin_page.wait_for_timeout(500)  # Small delay for Select2 to initialize

    select_select2_autocomplete(admin_page, f"id_2-{n}-autor", "Kowal", timeout=30000)

    # Wait for discipline to be auto-populated via AJAX
    wait_for_discipline_populated(admin_page, f"id_2-{n}-dyscyplina_naukowa")

    assert admin_page.locator(f"#id_2-{n}-dyscyplina_naukowa").input_value() == str(
        dyscyplina1.pk
    )


@pytest.mark.django_db(transaction=True)
def test_zglos_publikacje_wiele_klikniec_psuje_select2(
    admin_page: Page,
    channels_live_server,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    dyscyplina1,
    rok,
):
    """Test that multiple 'add author' clicks don't break Select2."""
    for autor in autor_jan_kowalski, autor_jan_nowak:
        Autor_Dyscyplina.objects.get_or_create(
            autor=autor, rok=rok, dyscyplina_naukowa=dyscyplina1
        )
        Autor_Jednostka.objects.get_or_create(autor=autor, jednostka=jednostka)

    admin_page.goto(
        channels_live_server.url + reverse("zglos_publikacje:nowe_zgloszenie")
    )
    admin_page.wait_for_load_state("domcontentloaded")
    admin_page.evaluate("if(window.Cookielaw) Cookielaw.accept()")

    admin_page.fill("[name='0-tytul_oryginalny']", "test")
    admin_page.select_option("[name='0-rodzaj_zglaszanej_publikacji']", "2")
    admin_page.fill("[name='0-strona_www']", "https://www.onet.pl/")
    admin_page.fill("[name='0-rok']", str(rok))
    admin_page.fill("[name='0-email']", "moj@email.pl")

    admin_page.click("#id-wizard-submit")
    admin_page.wait_for_load_state("domcontentloaded")

    # Click add-form multiple times (stress test)
    admin_page.click("#add-form")
    admin_page.wait_for_selector("#id_2-0-autor", state="visible")
    admin_page.click("#add-form")
    admin_page.wait_for_selector("#id_2-1-autor", state="visible")
    admin_page.click("#add-form")
    admin_page.wait_for_selector("#id_2-2-autor", state="visible")

    select_select2_autocomplete(admin_page, "id_2-1-autor", "Kowal", timeout=30000)

    # Wait for discipline to be auto-populated via AJAX
    wait_for_discipline_populated(admin_page, "id_2-1-dyscyplina_naukowa")

    assert admin_page.locator("#id_2-1-dyscyplina_naukowa").input_value() == str(
        dyscyplina1.pk
    )


@pytest.mark.django_db(transaction=True)
def test_zglos_publikacje_z_plikiem_wiele_klikniec_psuje_select2(
    admin_page: Page,
    channels_live_server,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    dyscyplina1,
    rok,
):
    """Test multiple clicks stress test with file upload."""
    for autor in autor_jan_kowalski, autor_jan_nowak:
        Autor_Dyscyplina.objects.get_or_create(
            autor=autor, rok=rok, dyscyplina_naukowa=dyscyplina1
        )
        Autor_Jednostka.objects.get_or_create(autor=autor, jednostka=jednostka)

    admin_page.goto(
        channels_live_server.url + reverse("zglos_publikacje:nowe_zgloszenie")
    )
    admin_page.wait_for_load_state("domcontentloaded")
    admin_page.evaluate("if(window.Cookielaw) Cookielaw.accept()")

    admin_page.fill("[name='0-tytul_oryginalny']", "test")
    admin_page.select_option("[name='0-rodzaj_zglaszanej_publikacji']", "2")
    admin_page.fill("[name='0-rok']", str(rok))
    admin_page.fill("[name='0-email']", "moj@email.pl")

    admin_page.click("#id-wizard-submit")
    admin_page.wait_for_load_state("domcontentloaded")

    plik = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "example.pdf"))
    admin_page.set_input_files("[name='1-plik']", plik)

    admin_page.click("#id-wizard-submit")
    admin_page.wait_for_load_state("domcontentloaded")

    # Click add-form multiple times (stress test)
    admin_page.click("#add-form")
    admin_page.wait_for_selector("#id_2-0-autor", state="visible")
    admin_page.click("#add-form")
    admin_page.wait_for_selector("#id_2-1-autor", state="visible")
    admin_page.click("#add-form")
    admin_page.wait_for_selector("#id_2-2-autor", state="visible")

    select_select2_autocomplete(admin_page, "id_2-1-autor", "Kowal", timeout=30000)

    # Wait for discipline to be auto-populated via AJAX
    wait_for_discipline_populated(admin_page, "id_2-1-dyscyplina_naukowa")

    assert admin_page.locator("#id_2-1-dyscyplina_naukowa").input_value() == str(
        dyscyplina1.pk
    )
