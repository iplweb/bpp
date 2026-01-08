import pytest
from django.urls import reverse
from model_bakery import baker
from playwright.sync_api import Page

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte


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
    admin_page: Page,
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

    admin_page.goto(
        live_server.url + reverse(url, args=(model_inst.pk,)), timeout=60000
    )
    admin_page.wait_for_load_state("domcontentloaded")

    # Check if element is present in DOM (not necessarily visible)
    assert admin_page.locator("#id_autorzy_set-0-oswiadczenie_ken").count() > 0


@pytest.mark.parametrize(
    ("model", "url"),
    [
        (Wydawnictwo_Ciagle, "admin:bpp_wydawnictwo_ciagle_change"),
        (Wydawnictwo_Zwarte, "admin:bpp_wydawnictwo_zwarte_change"),
    ],
)
def test_oswiadczenie_ken_niewidoczne(
    admin_page: Page,
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

    admin_page.goto(
        live_server.url + reverse(url, args=(model_inst.pk,)), timeout=60000
    )
    admin_page.wait_for_load_state("domcontentloaded")

    assert 'type="hidden" name="autorzy_set-0-oswiadczenie_ken"' in admin_page.content()


@pytest.mark.parametrize(
    ("model", "url"),
    [
        (Wydawnictwo_Ciagle, "admin:bpp_wydawnictwo_ciagle_change"),
        (Wydawnictwo_Zwarte, "admin:bpp_wydawnictwo_zwarte_change"),
    ],
)
def test_oswiadczenie_ken_oba_zaznaczone_problem(
    admin_page: Page,
    live_server,
    model,
    url,
    pokazuj_oswiadczenia_ken,
    autor_jan_nowak,
    jednostka,
    charaktery_formalne,
    typy_odpowiedzialnosci,
):
    """Test that both KEN and PBN checkboxes cannot be selected together."""
    from bpp.tests import normalize_html

    model_inst = baker.make(model)
    model_inst.dodaj_autora(autor_jan_nowak, jednostka)

    admin_page.goto(
        live_server.url + reverse(url, args=(model_inst.pk,)), timeout=60000
    )
    admin_page.wait_for_load_state("domcontentloaded")

    # Scroll element into view and select
    admin_page.evaluate(
        """
        const elem = document.getElementById('id_autorzy_set-0-oswiadczenie_ken');
        elem.scrollIntoView();
    """
    )
    admin_page.select_option("#id_autorzy_set-0-oswiadczenie_ken", value="true")
    admin_page.check("#id_autorzy_set-0-upowaznienie_pbn")

    admin_page.click('input[name="_save"]')
    admin_page.wait_for_load_state("domcontentloaded")

    assert (
        "Pola 'Upoważnienie PBN' oraz 'Oświadczenie KEN' nie mogą być jednocześnie wybrane. Odznacz jedno lub drugie."
        in normalize_html(admin_page.content())
    )
