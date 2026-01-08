import pytest
from django.urls import reverse
from playwright.sync_api import Page

from bpp.tests import normalize_html


@pytest.mark.django_db
@pytest.mark.parametrize("klass", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_changelist_no_argument(klass, live_server, admin_page: Page):
    url = f"admin:bpp_{klass}_autor_changelist"
    admin_page.goto(live_server.url + reverse(url))
    assert "Musisz wejść w edycję" in normalize_html(admin_page.content())


@pytest.mark.django_db
@pytest.mark.parametrize("klass", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_edit_btn_invisible(klass, live_server, admin_page: Page):
    # Przy dodawaniu publikacji -- brak przycisku "edytuj autorów"
    url = f"admin:bpp_{klass}_add"
    admin_page.goto(live_server.url + reverse(url))
    assert "Edytuj autorów" not in normalize_html(admin_page.content())


@pytest.mark.parametrize(
    "klass,model",
    [
        ("wydawnictwo_ciagle", "Wydawnictwo_Ciagle"),
        ("wydawnictwo_zwarte", "Wydawnictwo_Zwarte"),
    ],
)
def test_edit_btn_appears(klass, model, live_server, admin_page: Page):
    # Przy edytowaniu publikacji -- przycisk "edytuj autorów" jest
    from model_bakery import baker

    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

    model_class = Wydawnictwo_Ciagle if model == "Wydawnictwo_Ciagle" else Wydawnictwo_Zwarte
    res = baker.make(model_class)

    url = f"admin:bpp_{klass}_change"
    admin_page.goto(live_server.url + reverse(url, args=(res.pk,)))

    baker.make(model_class)

    assert "Autorzy" in normalize_html(admin_page.content())


@pytest.mark.parametrize(
    "klass,model",
    [
        ("wydawnictwo_ciagle", "Wydawnictwo_Ciagle"),
        ("wydawnictwo_zwarte", "Wydawnictwo_Zwarte"),
    ],
)
def test_changeform_save(klass, model, admin_page: Page, live_server):
    from model_bakery import baker

    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

    model_class = Wydawnictwo_Ciagle if model == "Wydawnictwo_Ciagle" else Wydawnictwo_Zwarte
    rec = baker.make(model_class)
    wa = baker.make(model_class.autorzy.through, rekord=rec)

    url = f"admin:bpp_{klass}_autor_change"
    admin_page.goto(live_server.url + reverse(url, args=(wa.pk,)))

    admin_page.wait_for_selector('input[name="_save"]', state="visible")

    # wchodzimy z okreslonym ID na okreslony rekord, zapisujmey, czy jest OK ?
    admin_page.click('input[name="_save"]')
    admin_page.wait_for_load_state("domcontentloaded")

    assert "Dodaj powiązanie" in normalize_html(admin_page.content())


@pytest.mark.parametrize(
    "klass,model",
    [
        ("wydawnictwo_ciagle", "Wydawnictwo_Ciagle"),
        ("wydawnictwo_zwarte", "Wydawnictwo_Zwarte"),
    ],
)
def test_changelist_with_argument(klass, model, admin_page: Page, live_server):
    from model_bakery import baker

    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

    model_class = Wydawnictwo_Ciagle if model == "Wydawnictwo_Ciagle" else Wydawnictwo_Zwarte
    rec = baker.make(model_class)
    url = f"admin:bpp_{klass}_autor_changelist"
    admin_page.goto(live_server.url + reverse(url) + f"?rekord__id__exact={rec.pk}")

    assert "Dodaj powiązanie" in normalize_html(admin_page.content())

    # wchodzimy z okreslonym ID, czy jest lista autorów?
    admin_page.get_by_text("Edycja rekordu").click()
    admin_page.wait_for_load_state("domcontentloaded")

    assert "Autorzy" in normalize_html(admin_page.content())


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "klass,model",
    [
        ("wydawnictwo_ciagle", "Wydawnictwo_Ciagle"),
        ("wydawnictwo_zwarte", "Wydawnictwo_Zwarte"),
    ],
)
def test_changeform_add(
    klass,
    model,
    channels_live_server,
    admin_page: Page,
    autor_jan_nowak,
    jednostka,
    typy_odpowiedzialnosci,
):
    from model_bakery import baker

    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
    from django_bpp.playwright_util import select_select2_autocomplete

    model_class = (
        Wydawnictwo_Ciagle if model == "Wydawnictwo_Ciagle" else Wydawnictwo_Zwarte
    )
    assert model_class.autorzy.through.objects.count() == 0

    rec = baker.make(model_class)
    url = f"admin:bpp_{klass}_autor_changelist"
    admin_page.goto(
        channels_live_server.url + reverse(url) + f"?rekord__id__exact={rec.pk}"
    )

    admin_page.wait_for_selector('a[name="_add_wa"]', state="visible")
    admin_page.click('a[name="_add_wa"]')
    admin_page.wait_for_load_state("domcontentloaded")

    # Fill admin inline form - equivalent to fill_admin_inline
    prefix = "id_"
    select_select2_autocomplete(
        admin_page,
        f"{prefix}autor",
        f"{autor_jan_nowak.nazwisko} {autor_jan_nowak.imiona}",
        timeout=30000,
    )
    select_select2_autocomplete(
        admin_page, f"{prefix}jednostka", jednostka.nazwa, timeout=30000
    )
    select_select2_autocomplete(
        admin_page,
        f"{prefix}zapisany_jako",
        f"{autor_jan_nowak.nazwisko} {autor_jan_nowak.imiona}",
        timeout=30000,
    )

    admin_page.click('input[name="_save"]')
    admin_page.wait_for_load_state("domcontentloaded")

    assert "Edycja rekordu" in normalize_html(admin_page.content())

    assert model_class.autorzy.through.objects.count() == 1
