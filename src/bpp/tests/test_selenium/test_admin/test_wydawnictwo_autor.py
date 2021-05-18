import pytest
from django.urls import reverse
from model_mommy import mommy
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
from splinter.driver.webdriver.firefox import WebDriver

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from bpp.tests import fill_admin_inline, normalize_html

from django_bpp.selenium_util import wait_for_page_load


@pytest.mark.parametrize("klass", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_changelist_no_argument(klass, live_server, admin_browser: WebDriver):
    url = f"admin:bpp_{klass}_autor_changelist"
    admin_browser.visit(live_server + reverse(url))
    assert "Musisz wejść w edycję" in normalize_html(admin_browser.html)


@pytest.mark.parametrize("klass", ["wydawnictwo_ciagle", "wydawnictwo_zwarte"])
def test_edit_btn_invisible(klass, live_server, admin_browser: WebDriver):
    # Przy dodawaniu publikacji -- brak przycisku "edytuj autorów"
    url = f"admin:bpp_{klass}_add"
    admin_browser.visit(live_server + reverse(url))
    assert "Edytuj autorów" not in normalize_html(admin_browser.html)


@pytest.mark.parametrize(
    "klass,model",
    [
        ("wydawnictwo_ciagle", Wydawnictwo_Ciagle),
        ("wydawnictwo_zwarte", Wydawnictwo_Zwarte),
    ],
)
def test_edit_btn_appears(klass, model, live_server, admin_browser: WebDriver):
    # Przy edytowaniu publikacji -- przycisk "edytuj autorów" jest
    res = mommy.make(model)

    url = f"admin:bpp_{klass}_change"
    admin_browser.visit(live_server + reverse(url, args=(res.pk,)))

    mommy.make(model)

    assert "Edycja autorów" in normalize_html(admin_browser.html)


@pytest.mark.parametrize(
    "klass,model",
    [
        ("wydawnictwo_ciagle", Wydawnictwo_Ciagle),
        ("wydawnictwo_zwarte", Wydawnictwo_Zwarte),
    ],
)
def test_changelist_with_argument(klass, model, admin_browser, live_server):
    rec = mommy.make(model)
    url = f"admin:bpp_{klass}_autor_changelist"
    admin_browser.visit(live_server + reverse(url) + f"?rekord__id__exact={rec.pk}")

    assert "Dodaj powiązanie" in normalize_html(admin_browser.html)

    # wchodzimy z okreslonym ID, czy jest lista autorów?
    with wait_for_page_load(admin_browser):
        admin_browser.find_by_text("Edycja rekordu").click()

    assert "Edycja autorów" in normalize_html(admin_browser.html)


@pytest.mark.parametrize(
    "klass,model",
    [
        ("wydawnictwo_ciagle", Wydawnictwo_Ciagle),
        ("wydawnictwo_zwarte", Wydawnictwo_Zwarte),
    ],
)
def test_changeform_save(klass, model, admin_browser, live_server):
    rec = mommy.make(model)
    wa = mommy.make(model.autorzy.through, rekord=rec)

    url = f"admin:bpp_{klass}_autor_change"

    admin_browser.visit(live_server + reverse(url, args=(wa.pk,)))

    WebDriverWait(admin_browser.driver, 10).until(
        expected_conditions.presence_of_element_located((By.NAME, "_save"))
    )

    # wchodzimy z okreslonym ID na okreslony rekord, zapisujmey, czy jest OK ?
    with wait_for_page_load(admin_browser):
        admin_browser.find_by_name("_save").click()

    assert "Dodaj powiązanie" in normalize_html(admin_browser.html)


@pytest.mark.parametrize(
    "klass,model",
    [
        ("wydawnictwo_ciagle", Wydawnictwo_Ciagle),
        ("wydawnictwo_zwarte", Wydawnictwo_Zwarte),
    ],
)
def test_changeform_add(
    klass,
    model,
    live_server,
    admin_browser,
    autor_jan_nowak,
    jednostka,
    typy_odpowiedzialnosci,
):
    assert model.autorzy.through.objects.count() == 0

    rec = mommy.make(model)
    url = f"admin:bpp_{klass}_autor_changelist"
    admin_browser.visit(live_server + reverse(url) + f"?rekord__id__exact={rec.pk}")

    with wait_for_page_load(admin_browser):
        admin_browser.find_by_name("_add_wa").click()

    fill_admin_inline(admin_browser, autor_jan_nowak, jednostka, prefix="id_")

    with wait_for_page_load(admin_browser):
        admin_browser.find_by_name("_save").click()

    assert "Edycja rekordu" in normalize_html(admin_browser.html)

    assert model.autorzy.through.objects.count() == 1
