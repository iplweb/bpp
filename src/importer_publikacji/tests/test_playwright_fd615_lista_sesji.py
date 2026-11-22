"""FD#615 — lista sesji importu w przeglądarce: szybki filtr „Tylko błędy
importu”, sortowanie i filtry w adresie URL, przywrócenie widoku po powrocie
z kafelków importera z komunikatem i przyciskiem „Wyczyść”."""

import re

import pytest
from playwright.sync_api import Page, expect

from importer_publikacji.models import ImportSession

S = ImportSession.Status
LISTA = "/importer_publikacji/sessions/"


def _sesja(user, status, tytul):
    return ImportSession.objects.create(
        created_by=user,
        provider_name="CrossRef",
        identifier=f"10.1/{tytul}",
        raw_data={},
        normalized_data={"title": tytul, "doi": f"10.1/{tytul}"},
        status=status,
    )


@pytest.mark.playwright
def test_tylko_bledy_zapamietane_po_powrocie(
    channels_live_server, admin_page: Page, admin_user, uczelnia, transactional_db
):
    _sesja(admin_user, S.COMPLETED, "Praca zakonczona")
    _sesja(admin_user, S.IMPORT_FAILED, "Praca z bledem")
    _sesja(admin_user, S.FETCHED, "Praca w toku")

    page = admin_page
    page.goto(channels_live_server.url + LISTA)
    wiersze = page.locator("#sessions-table tbody tr")
    expect(wiersze).to_have_count(3)

    przycisk = page.locator("#session-filter-tylko-bledy")
    expect(przycisk).to_have_attribute("aria-pressed", "false")
    przycisk.click()

    expect(page).to_have_url(re.compile(r"status=import_failed"))
    expect(wiersze).to_have_count(1)
    expect(wiersze.first).to_contain_text("Praca z bledem")
    expect(page.locator("#session-filter-tylko-bledy")).to_have_attribute(
        "aria-pressed", "true"
    )

    # Sortowanie klikiem w nagłówek trafia do adresu URL.
    page.locator("#sessions-table thead th", has_text="Źródło").click()
    expect(page).to_have_url(re.compile(r"sort=(-)?provider_name"))

    # Powrót przez kafelki importera i link „Importy w toku / ostatnie”.
    page.goto(channels_live_server.url + "/importer_publikacji/")
    page.locator("#import-sessions-link").click()

    komunikat = page.locator("#session-list-przywrocone")
    expect(komunikat).to_contain_text("Pokazuję zapamiętane filtry")
    expect(komunikat).to_contain_text("Status: Błąd importu")
    expect(page).to_have_url(re.compile(r"status=import_failed"))
    expect(wiersze).to_have_count(1)

    page.locator("#session-filter-wyczysc").click()
    expect(page.locator("#session-list-przywrocone")).to_have_count(0)
    expect(wiersze).to_have_count(3)
    expect(page).to_have_url(re.compile(re.escape(LISTA) + r"$"))

    # Wybór wielokrotny: lista statusów zostaje otwarta między kliknięciami,
    # filtr działa po jej zamknięciu.
    page.wait_for_load_state("networkidle")
    page.locator("#session-filter-form .select2-selection--multiple").click()
    expect(page.locator(".select2-container--open")).not_to_have_count(0)
    page.locator(".select2-results__option", has_text="Zakończono").click()
    page.locator(".select2-results__option", has_text="Pobrano dane").click()
    expect(wiersze).to_have_count(3)
    # Zamknięcie listy kliknięciem obok.
    page.locator("h5", has_text="Sesje importu").click()
    expect(page).to_have_url(re.compile(r"status=completed"))
    expect(page).to_have_url(re.compile(r"status=fetched"))
    expect(wiersze).to_have_count(2)
    expect(page.locator(".select2-container--open")).to_have_count(0)
