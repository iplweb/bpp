"""FD#521: edytor zapytań źródła danych raportu, w przeglądarce.

Kolorowanie, „Formatuj” i podpowiadanie pól robi ``django-flexible-reports``
(>= 0.6.0); tu sprawdzamy, że całość działa w adminie BPP (Grappelli, schemat
``BppQLSchema``) — czyli kryterium ze zgłoszenia: po wpisaniu
``charakter_formalny.`` edytor podpowiada pola charakteru formalnego.
"""

import pytest
from playwright.sync_api import Page, expect

from django_bpp.playwright_util import wait_for_page_load

pytest.importorskip(
    "flexible_reports.query_format",
    reason="wymaga django-flexible-reports >= 0.6.0 (edytor zapytań)",
)

POLE = "#id_dsl_query"
PODPOWIEDZI = ".djangoql-completion"


def _otworz_nowe_zrodlo_danych(page: Page, live_server):
    page.goto(live_server.url + "/admin/flexible_reports/datasource/add/")
    wait_for_page_load(page)
    # Edytor doczepia się do pola po załadowaniu strony.
    page.wait_for_selector(POLE + "[data-fr-query-editor=on]", timeout=10000)
    # Schemat domyślnego modelu (Rekord) dociąga się osobnym żądaniem; bez
    # niego nie ma czego podpowiadać.
    page.wait_for_selector(".fr-query-hints:not([hidden])", timeout=10000)


def _oczekuj_podpowiedzi(page: Page, nazwa):
    expect(page.locator(PODPOWIEDZI).get_by_text(nazwa, exact=True)).to_be_visible(
        timeout=10000
    )


def _tekst_podpowiedzi(page: Page):
    return page.locator(PODPOWIEDZI + " li").all_inner_texts()


def test_fd521_podpowiada_pola_charakteru_formalnego(
    channels_live_server, admin_page: Page, transactional_db
):
    _otworz_nowe_zrodlo_danych(admin_page, channels_live_server)

    # Domyślnie wybrany jest Rekord (FD#522) — nic nie trzeba przestawiać.
    assert (
        "rekord"
        in admin_page.locator("#id_base_model option:checked").inner_text().lower()
    )

    admin_page.select_option("#id_query_language", "djangoql")
    admin_page.click(POLE)
    admin_page.keyboard.type("charakter_formalny.")

    # ``expect`` czeka: lista podpowiedzi odświeża się chwilę po wpisaniu
    # kropki (wcześniej pokazuje pola samego Rekordu).
    _oczekuj_podpowiedzi(admin_page, "nazwa")
    _oczekuj_podpowiedzi(admin_page, "skrot")
    # Pola Rekordu zniknęły z listy — podpowiadamy już model powiązany.
    assert "tytul_oryginalny" not in _tekst_podpowiedzi(admin_page)

    # Wpisany tekst jest pokolorowany (nazwa pola jako osobny token).
    assert admin_page.locator(".fr-query-code .fr-tok-name").count() >= 1


def test_fd521_enter_lamie_wiersz_a_nie_wysyla_formularza(
    channels_live_server, admin_page: Page, transactional_db
):
    _otworz_nowe_zrodlo_danych(admin_page, channels_live_server)
    adres = admin_page.url

    admin_page.select_option("#id_query_language", "djangoql")
    admin_page.click(POLE)
    admin_page.keyboard.type("rok = 2020")
    admin_page.keyboard.press("Escape")
    admin_page.keyboard.press("Enter")
    admin_page.keyboard.type("and rok")

    assert admin_page.locator(POLE).input_value().startswith("rok = 2020\nand rok")
    assert admin_page.url == adres


def test_fd521_formatuj_uklada_zapytanie(
    channels_live_server, admin_page: Page, transactional_db
):
    _otworz_nowe_zrodlo_danych(admin_page, channels_live_server)

    admin_page.select_option("#id_query_language", "djangoql")
    admin_page.fill(
        POLE,
        'rok >= 2020 and (charakter_formalny.skrot = "AC" '
        'or charakter_formalny.skrot = "KSP" or typ_kbn.skrot = "PO")',
    )
    admin_page.get_by_role("button", name="Formatuj").click()

    expect(admin_page.locator(POLE)).to_have_value(
        "rok >= 2020\n"
        "and (\n"
        '    charakter_formalny.skrot = "AC"\n'
        '    or charakter_formalny.skrot = "KSP"\n'
        '    or typ_kbn.skrot = "PO"\n'
        ")",
        timeout=10000,
    )


def test_fd521_zmiana_modelu_odswieza_podpowiedzi(
    channels_live_server, admin_page: Page, transactional_db
):
    _otworz_nowe_zrodlo_danych(admin_page, channels_live_server)
    admin_page.select_option("#id_query_language", "djangoql")

    with admin_page.expect_response(lambda r: "query-editor/schema" in r.url):
        admin_page.select_option("#id_base_model", label="BPP | autor")

    admin_page.click(POLE)
    admin_page.keyboard.type("nazwis")

    _oczekuj_podpowiedzi(admin_page, "nazwisko")


def test_fd521_django_dsl_pokazuje_liste_pol(
    channels_live_server, admin_page: Page, transactional_db
):
    _otworz_nowe_zrodlo_danych(admin_page, channels_live_server)

    # django-dsl jest językiem domyślnym: zamiast podpowiedzi przy pisaniu
    # pod polem jest lista pól modelu; kliknięcie wstawia nazwę do zapytania.
    lista = admin_page.locator(".fr-query-hints")
    expect(lista.locator("summary")).to_contain_text("Dostępne pola")
    lista.locator("summary").click()
    lista.get_by_role("button", name="rok", exact=True).click()

    assert admin_page.locator(POLE).input_value() == "rok"
