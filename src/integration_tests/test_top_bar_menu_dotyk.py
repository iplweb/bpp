"""FD#626: menu górne strony publicznej na ekranie dotykowym.

Na telefonie nie ma najechania kursorem. Podmenu wielokolumnowe („operacje”,
„ewaluacja”, „PBN”) otwierał wyłącznie ``:hover`` i skrypt na ``mouseenter``,
czyli to, co przeglądarka „dorobi” po stuknięciu. Skutki:

* stuknięcie tej samej pozycji drugi raz nie zamykało podmenu,
* po otwarciu podmenu wielokolumnowego zwykłe podmenu („redagowanie”,
  „konto”) otwierały się niewidoczne — skrypt myszy zostawiał im w atrybucie
  ``style`` ukrycie, które wygrywało z klasą ``is-active``,
* na telefonie blok wielokolumnowy był przypięty do swojej pozycji i wystawał
  poza ekran (druga kolumna „ewaluacji” ucięta),
* podmenu wyższe niż ekran wychodziło poza jego dolną krawędź.

Teraz dotyk ma własną ścieżkę (``src/bpp/static/bpp/js/top-bar-menu.js``):
stuknięcie przełącza klasę ``is-active``, stuknięcie obok ją zdejmuje.

Emulacja dotyku w Chromium (``has_touch``/``is_mobile``) to nie to samo, co
Safari na iPhonie — te testy pilnują logiki skryptu i układu, a nie
zachowania konkretnej przeglądarki.
"""

import pytest
from playwright.sync_api import Page, expect

from django_bpp.playwright_util import wait_for_page_load

TELEFON = dict(
    viewport={"width": 393, "height": 659},
    device_scale_factor=2,
    is_mobile=True,
    has_touch=True,
)
TABLET = dict(
    viewport={"width": 1080, "height": 810},
    device_scale_factor=2,
    is_mobile=True,
    has_touch=True,
)

POZYCJE_MENU = "#example-menu ul.dropdown.menu > li"
PODMENU = "xpath=./ul | ./div"
# Dłużej niż opóźnione chowanie podmenu po zjechaniu kursorem (500 ms):
# podmenu otwarte dotykiem ma po tym czasie nadal być otwarte.
PO_CZASIE_CHOWANIA_MS = 900


def _otworz_strone(page: Page, url: str) -> None:
    page.goto(url + "/")
    wait_for_page_load(page)
    page.evaluate("if (typeof Cookielaw !== 'undefined') { Cookielaw.accept(); }")
    wait_for_page_load(page)
    # Menu ukryte do inicjalizacji Foundation (klasa bpp-js-init).
    page.wait_for_function(
        "() => !document.documentElement.classList.contains('bpp-js-init')"
    )
    ikona = page.locator(".title-bar .menu-icon")
    if ikona.is_visible():
        ikona.tap()
    page.locator("#example-menu").wait_for(state="visible")


def _pozycja(page: Page, nazwa: str):
    return page.locator(POZYCJE_MENU).filter(
        has=page.locator(f"xpath=./a[contains(normalize-space(.), '{nazwa}')]")
    )


def _stuknij(pozycja) -> None:
    pozycja.locator("> a").tap()


def _podmenu(pozycja):
    return pozycja.locator(PODMENU).first


def _oczekuj_otwarte(podmenu) -> None:
    expect(podmenu).to_be_visible()
    expect(podmenu).to_have_css("opacity", "1")


def _oczekuj_zamkniete(podmenu) -> None:
    expect(podmenu).to_be_hidden()


def _linki_poza_ekranem(podmenu) -> list[str]:
    return podmenu.evaluate(
        """(e) => {
            const szer = document.documentElement.clientWidth;
            return [...e.querySelectorAll('a')].filter((a) => {
                const r = a.getBoundingClientRect();
                return r.left < 0 || r.right > szer + 1;
            }).map((a) => a.textContent.trim());
        }"""
    )


@pytest.mark.browser_context_args(**TELEFON)
def test_telefon_menu_wielokolumnowe_miesci_sie_i_da_sie_wybrac_pozycje(
    channels_live_server, admin_page: Page, uczelnia
):
    _otworz_strone(admin_page, channels_live_server.url)

    ewaluacja = _pozycja(admin_page, "ewaluacja")
    _stuknij(ewaluacja)
    podmenu = _podmenu(ewaluacja)
    _oczekuj_otwarte(podmenu)

    # Stuknięcie nie może otworzyć podmenu tylko na chwilę.
    admin_page.wait_for_timeout(PO_CZASIE_CHOWANIA_MS)
    _oczekuj_otwarte(podmenu)

    # Wszystkie pozycje (obie kolumny) mieszczą się na szerokość ekranu...
    assert _linki_poza_ekranem(podmenu) == []
    # ...a podmenu nie wychodzi poniżej ekranu (reszta przewija się w nim).
    dol = podmenu.evaluate("e => e.getBoundingClientRect().bottom")
    assert dol <= TELEFON["viewport"]["height"]

    # Ostatnia pozycja drugiej kolumny: trzeba do niej przewinąć podmenu.
    link = podmenu.locator("ul.column-2 li a").last
    cel = link.get_attribute("href")
    link.tap()
    admin_page.wait_for_url(f"**{cel}")


@pytest.mark.browser_context_args(**TELEFON)
def test_telefon_stukniecie_obok_i_ponowne_stukniecie_zamyka_menu(
    channels_live_server, admin_page: Page, uczelnia
):
    _otworz_strone(admin_page, channels_live_server.url)

    operacje = _pozycja(admin_page, "operacje")
    podmenu = _podmenu(operacje)

    _stuknij(operacje)
    _oczekuj_otwarte(podmenu)
    expect(operacje.locator("> a")).to_have_attribute("aria-expanded", "true")

    # Stuknięcie poza menu (napis „Menu” na pasku tytułowym) zamyka.
    admin_page.locator(".title-bar-title").tap()
    _oczekuj_zamkniete(podmenu)
    expect(operacje.locator("> a")).to_have_attribute("aria-expanded", "false")

    # Ponowne stuknięcie tej samej pozycji: otwiera, potem zamyka.
    _stuknij(operacje)
    _oczekuj_otwarte(podmenu)
    _stuknij(operacje)
    _oczekuj_zamkniete(podmenu)


@pytest.mark.browser_context_args(**TELEFON)
def test_telefon_po_menu_wielokolumnowym_dziala_zwykle_podmenu(
    channels_live_server, admin_page: Page, uczelnia
):
    _otworz_strone(admin_page, channels_live_server.url)

    operacje = _pozycja(admin_page, "operacje")
    redagowanie = _pozycja(admin_page, "redagowanie")

    _stuknij(operacje)
    _oczekuj_otwarte(_podmenu(operacje))

    # Zwykłe podmenu (Foundation) otwiera się widoczne, a poprzednie znika.
    _stuknij(redagowanie)
    _oczekuj_otwarte(_podmenu(redagowanie))
    _oczekuj_zamkniete(_podmenu(operacje))

    # ...i w drugą stronę.
    _stuknij(operacje)
    _oczekuj_otwarte(_podmenu(operacje))
    _oczekuj_zamkniete(_podmenu(redagowanie))

    _stuknij(redagowanie)
    link = _podmenu(redagowanie).locator("a", has_text="Import publikacji")
    cel = link.get_attribute("href")
    link.tap()
    admin_page.wait_for_url(f"**{cel}")


@pytest.mark.browser_context_args(**TABLET)
def test_tablet_stukniecie_pozycji_nie_przewija_strony_na_gore(
    channels_live_server, admin_page: Page, uczelnia
):
    """Pozycje z podmenu mają ``href="#"`` — kliknięcie przewijało stronę
    na samą górę, gubiąc miejsce, w którym był czytelnik. Na szerokim
    ekranie pasek menu jest przyklejony, więc da się go stuknąć także po
    przewinięciu strony."""
    _otworz_strone(admin_page, channels_live_server.url)
    # Strona główna pustej bazy bywa niższa niż ekran — wymuś przewijanie.
    admin_page.evaluate(
        "document.body.style.minHeight = '3000px'; window.scrollTo(0, 300);"
    )
    przed = admin_page.evaluate("window.scrollY")
    assert przed > 0

    operacje = _pozycja(admin_page, "operacje")
    _stuknij(operacje)
    _oczekuj_otwarte(_podmenu(operacje))
    admin_page.wait_for_timeout(300)

    assert admin_page.evaluate("window.scrollY") == przed
    assert not admin_page.url.endswith("#")


@pytest.mark.browser_context_args(**TABLET)
def test_tablet_menu_wielokolumnowe_na_dotyku(
    channels_live_server, admin_page: Page, uczelnia
):
    """Szeroki ekran dotykowy: pasek jak na komputerze (bez ikony menu),
    podmenu dwukolumnowe obok siebie — ale otwierane stuknięciem."""
    _otworz_strone(admin_page, channels_live_server.url)
    expect(admin_page.locator(".title-bar .menu-icon")).to_be_hidden()

    operacje = _pozycja(admin_page, "operacje")
    podmenu = _podmenu(operacje)

    _stuknij(operacje)
    _oczekuj_otwarte(podmenu)
    admin_page.wait_for_timeout(PO_CZASIE_CHOWANIA_MS)
    _oczekuj_otwarte(podmenu)
    assert _linki_poza_ekranem(podmenu) == []

    # Dwie kolumny obok siebie, nie jedna pod drugą.
    k1 = podmenu.locator("ul.column-1").bounding_box()
    k2 = podmenu.locator("ul.column-2").bounding_box()
    assert k2["x"] >= k1["x"] + k1["width"] - 1

    _stuknij(operacje)
    _oczekuj_zamkniete(podmenu)

    _stuknij(operacje)
    link = podmenu.locator("a", has_text="import dyscyplin")
    cel = link.get_attribute("href")
    link.tap()
    admin_page.wait_for_url(f"**{cel}")


def test_komputer_mysz_otwiera_i_chowa_menu_jak_dotad(
    channels_live_server, admin_page: Page, uczelnia
):
    """Strażnik: ścieżka myszy bez zmian — najechanie otwiera podmenu (zwykłe
    i wielokolumnowe), przejście na sąsiednią pozycję przełącza je od razu,
    zjechanie kursorem chowa, a kliknięcie pozycji w środku działa."""
    admin_page.set_viewport_size({"width": 1400, "height": 900})
    _otworz_strone(admin_page, channels_live_server.url)

    operacje = _pozycja(admin_page, "operacje")
    redagowanie = _pozycja(admin_page, "redagowanie")

    operacje.locator("> a").hover()
    _oczekuj_otwarte(_podmenu(operacje))

    redagowanie.locator("> a").hover()
    _oczekuj_otwarte(_podmenu(redagowanie))
    _oczekuj_zamkniete(_podmenu(operacje))

    operacje.locator("> a").hover()
    _oczekuj_otwarte(_podmenu(operacje))
    _oczekuj_zamkniete(_podmenu(redagowanie))

    # Kursor nad podmenu: zostaje otwarte dłużej niż czas chowania.
    _podmenu(operacje).locator("a", has_text="import dyscyplin").hover()
    admin_page.wait_for_timeout(PO_CZASIE_CHOWANIA_MS)
    _oczekuj_otwarte(_podmenu(operacje))

    # Zjechanie kursorem z menu chowa podmenu.
    admin_page.mouse.move(700, 850)
    _oczekuj_zamkniete(_podmenu(operacje))

    operacje.locator("> a").hover()
    link = _podmenu(operacje).locator("a", has_text="import dyscyplin")
    cel = link.get_attribute("href")
    link.click()
    admin_page.wait_for_url(f"**{cel}")
