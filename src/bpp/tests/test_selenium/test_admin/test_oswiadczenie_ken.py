import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from bpp.tests import normalize_html, show_element

from django_bpp.selenium_util import wait_for_page_load


@pytest.fixture
def nie_pokazuj_oswiadczen_ken(settings):
    settings.BPP_POKAZUJ_OSWIADCZENIE_KEN = False


@pytest.fixture
def pokazuj_oswiadczenia_ken(settings):
    settings.BPP_POKAZUJ_OSWIADCZENIE_KEN = True


@pytest.mark.parametrize(
    ("model", "url"),
    [
        (Wydawnictwo_Ciagle, "admin:bpp_wydawnictwo_ciagle_change"),
        (Wydawnictwo_Zwarte, "admin:bpp_wydawnictwo_zwarte_change"),
    ],
)
def test_oswiadczenie_ken_widoczne(
    admin_browser,
    live_server,
    model,
    url,
    pokazuj_oswiadczenia_ken,
    autor_jan_nowak,
    jednostka,
    charaktery_formalne,
    typy_odpowiedzialnosci,
):
    model_inst = baker.make(model)
    model_inst.dodaj_autora(autor_jan_nowak, jednostka)

    with wait_for_page_load(admin_browser):
        admin_browser.visit(live_server.url + reverse(url, args=(model_inst.pk,)))

    assert admin_browser.is_element_present_by_id("id_autorzy_set-0-oswiadczenie_ken")


@pytest.mark.parametrize(
    ("model", "url"),
    [
        (Wydawnictwo_Ciagle, "admin:bpp_wydawnictwo_ciagle_change"),
        (Wydawnictwo_Zwarte, "admin:bpp_wydawnictwo_zwarte_change"),
    ],
)
def test_oswiadczenie_ken_niewidoczne(
    admin_browser,
    live_server,
    model,
    url,
    nie_pokazuj_oswiadczen_ken,
    autor_jan_nowak,
    jednostka,
    charaktery_formalne,
    typy_odpowiedzialnosci,
):
    model_inst = baker.make(model)
    model_inst.dodaj_autora(autor_jan_nowak, jednostka)

    with wait_for_page_load(admin_browser):
        admin_browser.visit(live_server.url + reverse(url, args=(model_inst.pk,)))

    assert 'type="hidden" name="autorzy_set-0-oswiadczenie_ken"' in admin_browser.html


@pytest.mark.parametrize(
    ("model", "url"),
    [
        (Wydawnictwo_Ciagle, "admin:bpp_wydawnictwo_ciagle_change"),
        (Wydawnictwo_Zwarte, "admin:bpp_wydawnictwo_zwarte_change"),
    ],
)
def test_oswiadczenie_ken_oba_zaznaczone_problem(
    admin_browser,
    live_server,
    model,
    url,
    pokazuj_oswiadczenia_ken,
    autor_jan_nowak,
    jednostka,
    charaktery_formalne,
    typy_odpowiedzialnosci,
):
    model_inst = baker.make(model)
    model_inst.dodaj_autora(autor_jan_nowak, jednostka)

    with wait_for_page_load(admin_browser):
        admin_browser.visit(live_server.url + reverse(url, args=(model_inst.pk,)))

    show_element(
        admin_browser, admin_browser.find_by_id("id_autorzy_set-0-oswiadczenie_ken")
    )

    admin_browser.find_by_id("id_autorzy_set-0-oswiadczenie_ken").select("true")
    admin_browser.find_by_id("id_autorzy_set-0-upowaznienie_pbn").check()

    with wait_for_page_load(admin_browser):
        admin_browser.find_by_name("_save").click()

    assert (
        "Pola 'Upoważnienie PBN' oraz 'Oświadczenie KEN' nie mogą być jednocześnie wybrane. Odznacz jedno lub drugie."
        in normalize_html(admin_browser.html)
    )
