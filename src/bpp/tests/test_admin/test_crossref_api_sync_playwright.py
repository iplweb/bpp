import base64
import time

import pytest
from django.urls import reverse
from model_bakery import baker
from playwright.sync_api import Page

from bpp.models import Autor, Wydawnictwo_Ciagle


def _poll_until(page, predicate, timeout: float = 10.0, interval_ms: int = 100) -> bool:
    """Pompuj event-loop Playwrighta, aż ``predicate`` stanie się prawdziwy.

    Do pollingu MUSIMY użyć ``page.wait_for_timeout`` (nie ``time.sleep``) —
    ``time.sleep`` blokuje wątek testu, więc handlery route/dialogów
    Playwrighta nie mają szansy odpalić w trakcie pollingu i predykat
    (zależny od efektów po stronie serwera) nigdy nie zmienia stanu.
    Wzorzec: patrz ``test_clarivate._wait_for_dialog``.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        page.wait_for_timeout(interval_ms)
    return predicate()


@pytest.fixture
def autor_m():
    return baker.make(
        Autor,
        # base64, bo RODO:
        nazwisko=base64.decodebytes(b"TWllbG5pY3plaw==\n").decode("ascii"),
        imiona="Katarzyna",
    )


# UWAGA: testy w tym pliku celowo uzywaja ``live_server`` (WSGI, watek
# W PROCESIE testu), NIE ``channels_live_server`` (Daphne, subprocess).
# Kasety VCR (@pytest.mark.vcr) patchuja HTTP tylko w procesie testu —
# widok "pobierz z crossref" wykonuje zapytania do api.crossref.org
# server-side, wiec pod Daphne leci prawdziwy ruch sieciowy zamiast kaset.
@pytest.mark.vcr(ignore_localhost=True)
def test_crossref_api_autor_sync(
    admin_page: Page, live_server, transactional_db, autor_m
):
    admin_page.goto(
        live_server.url
        + reverse("admin:bpp_wydawnictwo_ciagle_add")
        + "../pobierz-z-crossref/"
    )

    admin_page.fill('input[name="identyfikator_doi"]', "10.12775/jehs.2022.12.07.045")

    try:
        admin_page.click("#id_submit")
        admin_page.wait_for_load_state("domcontentloaded")

        # Click the ORCID button for the first author
        admin_page.locator("#id_ustaw_orcid_button_author\\.0").first.click()

        # Wait for ORCID to be updated in database
        def check_orcid():
            autor_m.refresh_from_db()
            return autor_m.orcid == "0000-0003-2575-3642"

        # Poll until ORCID is updated (max 10 seconds, 100ms granularity).
        _poll_until(admin_page, check_orcid)

        assert check_orcid(), (
            f"Expected ORCID to be '0000-0003-2575-3642', got '{autor_m.orcid}'"
        )
    finally:
        autor_m.delete()


@pytest.fixture
def wydawnictwo_ciagle_jehs_2022():
    return baker.make(
        Wydawnictwo_Ciagle,
        doi="10.12775/jehs.2022.12.07.045",
        tytul_oryginalny="Neurological and neuropsychological post-covid complications",
    )


@pytest.fixture
def admin_page_strona_porownania(admin_page: Page, live_server):
    """Navigate to CrossRef comparison page and submit DOI search."""
    admin_page.goto(
        live_server.url
        + reverse("admin:bpp_wydawnictwo_ciagle_add")
        + "../pobierz-z-crossref/"
    )

    admin_page.fill('input[name="identyfikator_doi"]', "10.12775/jehs.2022.12.07.045")

    admin_page.click("#id_submit")
    admin_page.wait_for_load_state("domcontentloaded")

    return admin_page


@pytest.mark.vcr(ignore_localhost=True)
@pytest.mark.parametrize(
    "id_przycisku, atrybut, wynik",
    [
        ("id_ustaw_strony_button", "strony", "447-452"),
        ("id_ustaw_tom_button", "tom", "12"),
        ("id_ustaw_nr_zeszytu_button", "nr_zeszytu", "7"),
    ],
)
def test_crossref_api_strony_sync_browser(
    transactional_db,
    wydawnictwo_ciagle_jehs_2022,
    admin_page_strona_porownania: Page,
    id_przycisku,
    atrybut,
    wynik,
):
    """Test clicking buttons to sync strony/tom/nr_zeszytu from CrossRef."""
    # Click the button
    admin_page_strona_porownania.click(f"#{id_przycisku}")

    # Poll until attribute is updated in database (max 10 seconds).
    def check_attribute():
        wydawnictwo_ciagle_jehs_2022.refresh_from_db()
        return getattr(wydawnictwo_ciagle_jehs_2022, atrybut, None) == wynik

    _poll_until(admin_page_strona_porownania, check_attribute)

    assert check_attribute(), (
        f"Expected {atrybut} to be '{wynik}', "
        f"got '{getattr(wydawnictwo_ciagle_jehs_2022, atrybut, None)}'"
    )


@pytest.mark.vcr(ignore_localhost=True)
def test_crossref_api_streszczenie_sync_browser(
    transactional_db,
    wydawnictwo_ciagle_jehs_2022,
    admin_page_strona_porownania: Page,
):
    """Test clicking button to sync streszczenie (abstract) from CrossRef."""
    # Click the streszczenie button
    admin_page_strona_porownania.click("#id_ustaw_streszczenie_button")

    # Poll until streszczenie is created in database (max 10 seconds).
    def check_streszczenie():
        wydawnictwo_ciagle_jehs_2022.refresh_from_db()
        return wydawnictwo_ciagle_jehs_2022.streszczenia.exists()

    _poll_until(admin_page_strona_porownania, check_streszczenie)

    assert check_streszczenie(), "Expected streszczenie to be created"
