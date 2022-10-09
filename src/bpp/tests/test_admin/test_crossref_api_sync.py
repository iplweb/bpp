import base64

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Rekord, Wydawnictwo_Ciagle

from django_bpp.selenium_util import wait_for, wait_for_page_load


@pytest.fixture
def autor_m():
    return baker.make(
        Autor,
        # base64, bo RODO:
        nazwisko=base64.decodebytes(b"TWllbG5pY3plaw==\n").decode("ascii"),
        imiona="Katarzyna",
    )


@pytest.mark.vcr
def test_crossref_api_autor_wo_selenium(admin_app, autor_m):

    url = "/admin/bpp/wydawnictwo_ciagle/pobierz-z-crossref/"
    page = admin_app.get(url)
    page.forms[1]["identyfikator_doi"] = "10.12775/jehs.2022.12.07.045"
    page = page.forms[1].submit().maybe_follow()
    if b"id_ustaw_orcid_button_author.0" not in page.content:
        page.showbrowser()
        raise Exception


@pytest.mark.vcr(ignore_localhost=True)
@pytest.mark.flaky(reruns=1)
def test_crossref_api_autor_sync(admin_browser, live_server, transactional_db, autor_m):

    with wait_for_page_load(admin_browser):
        admin_browser.visit(
            live_server.url
            + reverse("admin:bpp_wydawnictwo_ciagle_add")
            + "../pobierz-z-crossref/"
        )

    admin_browser.find_by_name("identyfikator_doi").type("10.12775/jehs.2022.12.07.045")

    try:
        with wait_for_page_load(admin_browser):
            admin_browser.find_by_id("id_submit").click()

        admin_browser.find_by_id("id_ustaw_orcid_button_author.0")[0].click()

        def _():
            autor_m.refresh_from_db()
            return autor_m.orcid == "0000-0003-2575-3642"

        wait_for(_)
        assert True
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
def admin_browser_strona_porownania(admin_browser, live_server):
    with wait_for_page_load(admin_browser):
        admin_browser.visit(
            live_server.url
            + reverse("admin:bpp_wydawnictwo_ciagle_add")
            + "../pobierz-z-crossref/"
        )

    admin_browser.find_by_name("identyfikator_doi").type("10.12775/jehs.2022.12.07.045")

    with wait_for_page_load(admin_browser):
        admin_browser.find_by_id("id_submit").click()

    return admin_browser


@pytest.mark.django_db
@pytest.mark.vcr(ignore_localhost=True)
def test_crossref_api_strony_view(
    wydawnictwo_ciagle_jehs_2022,
    csrf_exempt_django_admin_app,
):

    csrf_exempt_django_admin_app.post(
        reverse("bpp:api_ustaw_strony"),
        {"rekord": Rekord.objects.all().first().form_post_pk, "strony": "447-452"},
    )

    wydawnictwo_ciagle_jehs_2022.refresh_from_db()

    return wydawnictwo_ciagle_jehs_2022.strony == "447-452"


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
    admin_browser_strona_porownania,
    id_przycisku,
    atrybut,
    wynik,
):
    # Kliknij id_przycisku, sprawdz czy atrybut wydawnictwa jest rowny do wynik
    admin_browser_strona_porownania.find_by_id(id_przycisku)[0].click()

    def _():
        wydawnictwo_ciagle_jehs_2022.refresh_from_db()
        return getattr(wydawnictwo_ciagle_jehs_2022, atrybut, None) == wynik

    wait_for(_)

    assert True


def test_crossref_api_streszczenie_sync_browser(
    transactional_db,
    wydawnictwo_ciagle_jehs_2022,
    live_server,
    admin_browser_strona_porownania,
):
    # Kliknij id_przycisku, sprawdz czy atrybut wydawnictwa jest rowny do wynik
    admin_browser_strona_porownania.find_by_id("id_ustaw_streszczenie_button").click()

    def _():
        wydawnictwo_ciagle_jehs_2022.refresh_from_db()
        return wydawnictwo_ciagle_jehs_2022.streszczenia.exists()

    wait_for(_)

    assert True
