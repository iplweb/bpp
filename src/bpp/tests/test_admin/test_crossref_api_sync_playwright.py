import base64

import pytest
from django.urls import reverse
from model_bakery import baker
from playwright.sync_api import Page

from bpp.models import Autor, Wydawnictwo_Ciagle


@pytest.fixture
def autor_m():
    return baker.make(
        Autor,
        # base64, bo RODO:
        nazwisko=base64.decodebytes(b"TWllbG5pY3plaw==\n").decode("ascii"),
        imiona="Katarzyna",
    )


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

        # Poll until ORCID is updated (max 10 seconds)
        for _ in range(20):
            if check_orcid():
                break
            admin_page.wait_for_timeout(500)

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
    live_server,
    admin_page_strona_porownania: Page,
    id_przycisku,
    atrybut,
    wynik,
):
    """Test clicking buttons to sync strony/tom/nr_zeszytu from CrossRef."""
    # Click the button
    admin_page_strona_porownania.click(f"#{id_przycisku}")

    # Poll until attribute is updated in database (max 10 seconds)
    def check_attribute():
        wydawnictwo_ciagle_jehs_2022.refresh_from_db()
        return getattr(wydawnictwo_ciagle_jehs_2022, atrybut, None) == wynik

    for _ in range(20):
        if check_attribute():
            break
        admin_page_strona_porownania.wait_for_timeout(500)

    assert check_attribute(), (
        f"Expected {atrybut} to be '{wynik}', "
        f"got '{getattr(wydawnictwo_ciagle_jehs_2022, atrybut, None)}'"
    )


@pytest.mark.vcr(ignore_localhost=True)
def test_crossref_api_streszczenie_sync_browser(
    transactional_db,
    wydawnictwo_ciagle_jehs_2022,
    live_server,
    admin_page_strona_porownania: Page,
):
    """Test clicking button to sync streszczenie (abstract) from CrossRef."""
    # Click the streszczenie button
    admin_page_strona_porownania.click("#id_ustaw_streszczenie_button")

    # Poll until streszczenie is created in database (max 10 seconds)
    def check_streszczenie():
        wydawnictwo_ciagle_jehs_2022.refresh_from_db()
        return wydawnictwo_ciagle_jehs_2022.streszczenia.exists()

    for _ in range(20):
        if check_streszczenie():
            break
        admin_page_strona_porownania.wait_for_timeout(500)

    assert check_streszczenie(), "Expected streszczenie to be created"
