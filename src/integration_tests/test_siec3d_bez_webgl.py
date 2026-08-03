"""Widok 3D sieci powiązań na przeglądarce BEZ WebGL-a (Rollbar #4006).

Przed poprawką ``new THREE.WebGLRenderer`` rzucał "Error creating WebGL
context." jako nieobsłużony wyjątek, a użytkownik dostawał czarny prostokąt
bez słowa wyjaśnienia. Zgłoszenia szły z crawlera ``meta-externalagent``
(headless Chrome bez GPU), ale ta sama ścieżka dotyczy sesji zdalnego
pulpitu, maszyn wirtualnych i przeglądarek z wyłączoną akceleracją.

Test celowo idzie przez PRAWDZIWĄ przeglądarkę i PRAWDZIWY bundle
(``dist/three-bundle.js``), bo testy jednostkowe w ``tests/js/`` importują
moduły ze źródła i nie widzą ani kroku esbuilda, ani sklejenia z szablonem
Django. Dwa błędy w tej poprawce — niedokończony refaktor w bundlu oraz
atrybut ``data-url-2d``, który nie mapuje się na ``dataset.url2d`` — były
niewidoczne dla vitesta i wyszły dopiero tutaj.

WYMAGANIE WSTĘPNE: ``make assets`` (bez zbudowanego bundla strona nie ma
czego wykonać i test padnie na braku komunikatu).
"""

import pytest
from django.urls import reverse
from model_bakery import baker
from playwright.sync_api import Page, expect

from bpp.models import Autor

# Zdejmujemy WebGL-a ZANIM wystartują skrypty strony — `add_init_script`
# wykonuje się przed każdym skryptem dokumentu, więc `three-entry.js` widzi
# już spreparowane `getContext`. Robimy to zamiast flag startowych
# przeglądarki (`--disable-webgl`), żeby nie dotykać współdzielonej w sesji
# instancji Chromium: inne testy Playwrighta w tym samym przebiegu mają
# dostać przeglądarkę nietkniętą.
BEZ_WEBGL = """
    const oryginalny = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (nazwa) {
        if (nazwa === "webgl" || nazwa === "webgl2"
                || nazwa === "experimental-webgl") {
            return null;
        }
        return oryginalny.apply(this, arguments);
    };
"""


@pytest.mark.django_db(transaction=True)
def test_widok_3d_bez_webgl_pokazuje_komunikat_zamiast_wyjatku(
    channels_live_server,
    page: Page,
    transactional_db,
):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)

    bledy_strony = []
    page.on("pageerror", lambda e: bledy_strony.append(str(e)))

    page.add_init_script(BEZ_WEBGL)
    url = reverse("bpp:browse_autor_powiazania_3d", args=[autor.pk])
    page.goto(f"{channels_live_server.url}{url}", wait_until="domcontentloaded")

    kontener = page.locator("#siec3d-container")

    # 1. Użytkownik dostaje wyjaśnienie, a nie czarny prostokąt.
    expect(kontener).to_contain_text("Widok 3D jest niedostępny", timeout=15000)

    # 2. …oraz działające wyjście awaryjne do widoku 2D.
    link = kontener.locator("a")
    expect(link).to_have_attribute(
        "href", reverse("bpp:browse_autor_powiazania", args=[autor.pk])
    )

    # 3. Sedno zgłoszenia #4006: żaden wyjątek nie ucieka do window.onerror,
    #    więc Rollbar nie dostaje już nic z tej ścieżki.
    assert bledy_strony == [], f"nieobsłużone wyjątki na stronie: {bledy_strony}"

    # 4. Renderer w ogóle nie powstał — sonda ubiegła Three.js.
    assert kontener.locator("canvas").count() == 0
