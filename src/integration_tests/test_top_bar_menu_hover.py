"""Najechanie myszą na pozycję podmenu w górnym pasku nie może zmieniać
szerokości rozwiniętego menu.

Pozycja podmenu po najechaniu przesuwa się lekko w prawo (wcięcie). Kiedyś
robił to sam ``padding-left``, więc najdłuższa pozycja poszerzała się
o kilka pikseli, a razem z nią całe menu wielokolumnowe
(``.menu-columns-wrapper`` ma ``width: max-content``) — ramka menu
„skakała". Teraz wcięcie zabiera tyle samo z ``padding-right`` (mixin
``menu-hover-indent`` w ``src/bpp/static/scss/top_bar.scss``).

Przejścia CSS są w teście wyłączone: stan po najechaniu jest od razu
końcowy, więc pomiar nie zależy od czasu animacji.
"""

from playwright.sync_api import Page

from django_bpp.playwright_util import wait_for_page_load

# Wstrzykiwane skryptem startowym, więc przetrwa także ewentualne
# przeładowanie strony (np. po akceptacji cookies).
BEZ_ANIMACJI = """
document.addEventListener("DOMContentLoaded", () => {
    const s = document.createElement("style");
    s.textContent = "*, *::before, *::after { transition: none !important; }";
    document.head.appendChild(s);
});
"""

POZYCJE_MENU = "#example-menu ul.dropdown.menu > li"
PODMENU = "xpath=./ul | ./div"


def _szerokosc(locator) -> float:
    return locator.evaluate("e => e.getBoundingClientRect().width")


def test_hover_pozycji_podmenu_nie_zmienia_szerokosci_menu(
    channels_live_server, admin_page: Page, uczelnia
):
    admin_page.set_viewport_size({"width": 1400, "height": 900})
    admin_page.add_init_script(BEZ_ANIMACJI)
    admin_page.goto(channels_live_server.url + "/")
    wait_for_page_load(admin_page)
    admin_page.evaluate("if (typeof Cookielaw !== 'undefined') { Cookielaw.accept(); }")
    wait_for_page_load(admin_page)
    admin_page.locator("#example-menu").wait_for(state="visible")

    pozycje = admin_page.locator(POZYCJE_MENU)
    sprawdzone_wielokolumnowe = 0
    zmiany = []

    for i in range(pozycje.count()):
        li = pozycje.nth(i)
        if li.locator(PODMENU).count() == 0:
            continue  # pozycja bez podmenu, np. logo „BPP"
        nazwa = li.locator("> a").inner_text().strip()
        li.locator("> a").hover()
        podmenu = li.locator(PODMENU).first
        podmenu.wait_for(state="visible")
        if "menu-columns-wrapper" in (podmenu.get_attribute("class") or ""):
            sprawdzone_wielokolumnowe += 1

        szerokosc_bez_hover = _szerokosc(podmenu)
        linki = podmenu.locator("li > a:visible")
        for j in range(linki.count()):
            link = linki.nth(j)
            wciecie_przed = link.evaluate("e => getComputedStyle(e).paddingLeft")
            link.hover()
            wciecie_po = link.evaluate("e => getComputedStyle(e).paddingLeft")
            # Pewność, że hover naprawdę zadziałał (efekt wcięcia jest).
            assert wciecie_po != wciecie_przed, (nazwa, link.inner_text())

            szerokosc = _szerokosc(podmenu)
            if abs(szerokosc - szerokosc_bez_hover) > 0.5:
                zmiany.append(
                    (nazwa, link.inner_text().strip(), szerokosc_bez_hover, szerokosc)
                )

        admin_page.mouse.move(5, 850)

    assert sprawdzone_wielokolumnowe > 0, "brak menu wielokolumnowych w teście"
    assert not zmiany, zmiany
