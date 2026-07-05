"""Playwright: prawy panel „Źródło docelowe" na stronie przemapowania.

Weryfikuje pełny pipeline JS (przemapuj.js): po wejściu z parametrem
`zrodlo_docelowe` (albo po zmianie comboboxa) panel doczytuje AJAX-em
parametry źródła docelowego, podświetla zgodność ISSN i — dla źródła
ministerialnego — ostrzega o niezgodnym MNiSW ID.
"""

from django.urls import reverse
from model_bakery import baker
from playwright.sync_api import Page

from django_bpp.playwright_util import wait_for_page_load


def _setup_zrodla():
    """Źródło ministerialne (3 publikacje) + cel zgodny (to samo MNiSW ID i
    ISSN) + cel bez MNiSW ID."""
    from pbn_api.models import Journal

    j_src = baker.make(Journal, mniswId=12345, status="CURRENT", title="JSrc")
    j_dst = baker.make(Journal, mniswId=12345, status="CURRENT", title="JDstOK")
    src = baker.make(
        "bpp.Zrodlo",
        nazwa="Src ministerialne",
        skrot="SrcSkrot",
        issn="1111-2222",
        e_issn="3333-4444",
        pbn_uid=j_src,
    )
    dst_ok = baker.make(
        "bpp.Zrodlo", nazwa="Cel zgodny", issn="1111-2222", pbn_uid=j_dst
    )
    dst_bad = baker.make("bpp.Zrodlo", nazwa="Cel bez MNiSW", issn="9999-0000")
    baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=src, _quantity=3)
    return src, dst_ok, dst_bad


def _url(server, src, zrodlo_docelowe=None):
    path = reverse("przemapuj_zrodlo:przemapuj", args=[src.slug])
    url = server.url + path
    if zrodlo_docelowe is not None:
        url += f"?zrodlo_docelowe={zrodlo_docelowe}"
    return url


def test_panel_docelowy_wypelnia_sie_i_podswietla_zgodnosc(
    channels_live_server, admin_page: Page, transactional_db
):
    src, dst_ok, _ = _setup_zrodla()

    admin_page.goto(_url(channels_live_server, src, dst_ok.pk))
    wait_for_page_load(admin_page)

    # Panel doczytuje dane celu (fetch → fill).
    admin_page.wait_for_selector("#dst-content", state="visible", timeout=15000)
    admin_page.wait_for_function(
        "() => document.getElementById('dst-nazwa').textContent.trim()"
        " === 'Cel zgodny'",
        timeout=15000,
    )

    # BPP ID i liczba publikacji celu (0).
    assert admin_page.text_content("#dst-bppid").strip() == str(dst_ok.pk)
    assert admin_page.text_content("#dst-liczba").strip() == "0"

    # ISSN identyczny jak źródłowy → podświetlony jako zgodny.
    klasy = admin_page.get_attribute("#dst-issn", "class") or ""
    assert "przemapuj-match" in klasy

    # MNiSW zgodne (to samo ID) → brak ostrzeżenia.
    assert admin_page.is_hidden("#dst-mnisw-warning")


def test_panel_docelowy_ostrzega_o_niezgodnym_mnisw(
    channels_live_server, admin_page: Page, transactional_db
):
    src, _, dst_bad = _setup_zrodla()

    admin_page.goto(_url(channels_live_server, src, dst_bad.pk))
    wait_for_page_load(admin_page)

    admin_page.wait_for_function(
        "() => document.getElementById('dst-nazwa').textContent.trim()"
        " === 'Cel bez MNiSW'",
        timeout=15000,
    )

    # Źródło ministerialne → cel bez MNiSW ID: ostrzeżenie o odrzuceniu.
    admin_page.wait_for_selector("#dst-mnisw-warning", state="visible", timeout=15000)


def test_panel_docelowy_admin_link_data_i_badge_wieku(
    channels_live_server, admin_page: Page, transactional_db
):
    """Po wczytaniu celu panel pokazuje link do admina, datę ostatniej
    modyfikacji oraz badge wieku (źródło ma niższy pk = utworzone wcześniej)."""
    from django.urls import reverse as dj_reverse

    src, dst_ok, _ = _setup_zrodla()  # src powstaje przed dst_ok → src.pk < dst_ok.pk

    admin_page.goto(_url(channels_live_server, src, dst_ok.pk))
    wait_for_page_load(admin_page)

    admin_page.wait_for_selector("#dst-content", state="visible", timeout=15000)
    admin_page.wait_for_function(
        "() => document.getElementById('dst-nazwa').textContent.trim()"
        " === 'Cel zgodny'",
        timeout=15000,
    )

    # Link do admina celu.
    admin_href = admin_page.get_attribute("#dst-admin-link", "href") or ""
    assert dj_reverse("admin:bpp_zrodlo_change", args=[dst_ok.pk]) in admin_href

    # Data ostatniej modyfikacji — niepusta (nie „—").
    zmien = admin_page.text_content("#dst-zmien").strip()
    assert zmien and zmien != "—"

    # Badge wieku: src (niższy pk) = wcześniej, dst = później.
    admin_page.wait_for_selector("#src-wiek", state="visible", timeout=15000)
    admin_page.wait_for_selector("#dst-wiek", state="visible", timeout=15000)
    assert "wcześniej" in admin_page.text_content("#src-wiek")
    assert "później" in admin_page.text_content("#dst-wiek")


def test_panel_docelowy_reaguje_na_zmiane_selecta(
    channels_live_server, admin_page: Page, transactional_db
):
    src, dst_ok, _ = _setup_zrodla()

    admin_page.goto(_url(channels_live_server, src))
    wait_for_page_load(admin_page)

    # Bez parametru — placeholder widoczny, treść ukryta.
    admin_page.wait_for_selector("#dst-placeholder", state="visible", timeout=15000)
    assert admin_page.is_hidden("#dst-content")

    # Symuluj wybór celu w comboboxie: ustaw wartość i wyemituj jQuery-owe
    # 'change' — dokładnie tak, jak robi to DAL Select2.
    admin_page.evaluate(
        """(pk) => {
            const s = document.getElementById('id_zrodlo_docelowe');
            if (!s.querySelector('option[value="' + pk + '"]')) {
                const o = document.createElement('option');
                o.value = pk; o.text = 'cel'; o.selected = true; s.appendChild(o);
            }
            s.value = pk;
            if (window.jQuery) { window.jQuery(s).trigger('change'); }
            else { s.dispatchEvent(new Event('change')); }
        }""",
        str(dst_ok.pk),
    )

    admin_page.wait_for_selector("#dst-content", state="visible", timeout=15000)
    admin_page.wait_for_function(
        "() => document.getElementById('dst-nazwa').textContent.trim()"
        " === 'Cel zgodny'",
        timeout=15000,
    )
