"""FD#587 (UI): link „Przejdź do pierwszego błędu” w formularzu admina
i zwijana kolumna „Zmiana” w porównaniu wersji."""

import reversion
from django.urls import reverse
from model_bakery import baker
from playwright.sync_api import Page, expect
from reversion.models import Version

from bpp.models import Seria_Wydawnicza
from django_bpp.playwright_util import wait_for_page_load


def _wyslij_pusty_formularz_autora(page, url):
    page.goto(url + "/admin/bpp/autor/add/")
    wait_for_page_load(page)
    page.locator("input[name='_save']").first.click()
    wait_for_page_load(page)
    expect(page.locator(".errornote")).to_be_visible()


def test_link_do_bledu_niewidoczny_gdy_blad_jest_na_ekranie(
    channels_live_server, admin_page: Page, transactional_db
):
    admin_page.set_viewport_size({"width": 1400, "height": 1200})
    _wyslij_pusty_formularz_autora(admin_page, channels_live_server.url)
    # Pole z błędem widać od razu pod komunikatem — nie ma po co klikać.
    expect(admin_page.locator(".bpp-do-pierwszego-bledu")).to_be_hidden()


def test_link_do_bledu_przewija_i_ustawia_kursor(
    channels_live_server, admin_page: Page, transactional_db
):
    admin_page.set_viewport_size({"width": 1400, "height": 260})
    _wyslij_pusty_formularz_autora(admin_page, channels_live_server.url)
    link = admin_page.locator(".bpp-do-pierwszego-bledu")
    expect(link).to_be_visible()
    link.click()
    # Kursor w polu leżącym w wierszu z błędem.
    w_bledzie = admin_page.evaluate(
        "() => { const el = document.activeElement;"
        " const w = el && el.closest('.grp-errors, .grp-row, .form-row');"
        " return !!w && (w.classList.contains('grp-errors')"
        " || !!w.querySelector('.errorlist')); }"
    )
    assert w_bledzie


def test_kolumna_zmiana_zwija_sie_do_strzalki(
    channels_live_server, admin_page: Page, transactional_db
):
    seria = baker.make(Seria_Wydawnicza, nazwa="Stara nazwa")
    with reversion.create_revision():
        seria.save()
    seria.nazwa = "Nowa nazwa"
    with reversion.create_revision():
        seria.save()
    nowsza, starsza = Version.objects.get_for_object(seria)[:2]

    admin_page.goto(
        channels_live_server.url
        + reverse("admin:bpp_seria_wydawnicza_compare", args=(seria.pk,))
        + f"?version_id1={starsza.pk}&version_id2={nowsza.pk}"
    )
    wait_for_page_load(admin_page)
    admin_page.evaluate(
        "() => localStorage.removeItem('bpp-porownanie-zmiana-zwinieta')"
    )

    roznica = admin_page.locator("td.bpp-kol-zmiana-diff del").first
    expect(roznica).to_be_visible()
    admin_page.locator(".bpp-przelacz-zmiane").click()
    expect(roznica).to_be_hidden()
    expect(admin_page.locator("table.bpp-porownanie")).to_have_class(
        "grp-table bpp-porownanie bpp-zmiana-zwinieta"
    )
    admin_page.locator(".bpp-przelacz-zmiane").click()
    expect(roznica).to_be_visible()
