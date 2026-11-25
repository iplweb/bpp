"""Podpowiedzi DjangoQL nie mogą interpretować nazw z bazy jako HTML.

Widżet podpowiedzi wstawia etykiety przez ``innerHTML``. Etykietami bywają
nazwy obiektów wpisane przez redaktorów (charakter formalny, źródło,
jednostka…), więc znaczniki w nazwie nie mogą trafić do strony jako znaczniki
— mają być pokazane jako zwykły tekst.
"""

import pytest
from model_bakery import baker
from playwright.sync_api import Page, expect

from bpp.models import Charakter_Formalny
from django_bpp.playwright_util import wait_for_page_load

# Znacznik, który po zinterpretowaniu jako HTML ustawia flagę na stronie.
ZNACZNIK = '<img src=x onerror="window.dqlHtmlWykonany=1">'
NAZWA = "Zly " + ZNACZNIK + " charakter"

PODPOWIEDZI = ".djangoql-completion"


@pytest.fixture
def charakter_ze_znacznikiem(transactional_db):
    return baker.make(Charakter_Formalny, nazwa=NAZWA, skrot="ZLY")


def _sprawdz_ze_znacznik_jest_tekstem(page: Page):
    lista = page.locator(PODPOWIEDZI)
    # Podpowiedź jest na liście i pokazuje nazwę DOSŁOWNIE, ze znakami < >.
    expect(lista.get_by_text("onerror", exact=False).first).to_be_visible(timeout=10000)
    assert ZNACZNIK in lista.inner_text()
    # W liście nie powstał żaden element z nazwy…
    assert lista.locator("img").count() == 0
    # …i nic się nie wykonało.
    page.wait_for_timeout(300)
    assert page.evaluate("() => window.dqlHtmlWykonany") is None


def test_podpowiedzi_w_wyszukiwarce_admina(
    channels_live_server, admin_page: Page, charakter_ze_znacznikiem
):
    admin_page.goto(channels_live_server.url + "/admin/bpp/wydawnictwo_ciagle/")
    wait_for_page_load(admin_page)
    admin_page.wait_for_selector("textarea[name=q]", timeout=10000)
    toggle = admin_page.locator("input.djangoql-toggle")
    if toggle.count() and not toggle.is_checked():
        toggle.check()

    admin_page.click("textarea[name=q]")
    admin_page.keyboard.type('charakter_formalny__rel = "Zly')

    _sprawdz_ze_znacznik_jest_tekstem(admin_page)


def test_podpowiedzi_w_szukaj_zapytaniem(
    channels_live_server, admin_page: Page, charakter_ze_znacznikiem
):
    admin_page.goto(channels_live_server.url + "/bpp/zapytanie/")
    wait_for_page_load(admin_page)
    pole = admin_page.locator("textarea").first
    pole.wait_for(timeout=10000)

    pole.click()
    admin_page.keyboard.type('charakter_formalny__rel = "Zly')

    _sprawdz_ze_znacznik_jest_tekstem(admin_page)
