"""Ciemne warianty motywów (_tryb-ciemny.scss): app-blue-auto, app-blue-ciemny.

Patrz docs/deweloper/budowanie-css.md, sekcja „Tryb ciemny”.
"""

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.staticfiles import finders

KORZEN = Path(__file__).resolve().parents[3]
SCSS = KORZEN / "src" / "bpp" / "static" / "scss"

CIEMNE_WARIANTY = [
    f"app-{kolor}-{wariant}"
    for kolor in ("blue", "green", "orange", "vizja", "mwsl", "uafm")
    for wariant in ("auto", "ciemny")
]


def _motywy():
    return [wartosc for wartosc, _etykieta in settings.BPP_THEMES]


def test_ciemne_warianty_sa_w_bpp_themes():
    motywy = _motywy()
    for motyw in CIEMNE_WARIANTY:
        assert motyw in motywy
    # Dotychczasowy motyw zostaje — istniejące uczelnie niczego nie zauważą.
    assert "app-blue" in motywy


def _motywy_reczne():
    """Motywy pisane ręcznie (app-*.scss). Motywy z konfiguratora wyglądu
    (scss/motywy/*.json) kompiluje task Grunta `motywy` — bez pliku .scss
    i bez targetu w Gruntfile.js."""
    return [w for w, _ in settings.BPP_THEMES if (SCSS / f"{w}.scss").exists()]


def test_motywy_reczne_obejmuja_ciemne_warianty():
    for motyw in CIEMNE_WARIANTY + ["app-blue"]:
        assert motyw in _motywy_reczne()


@pytest.mark.parametrize("motyw", _motywy_reczne())
def test_kazdy_motyw_ma_zrodlo_scss_i_cel_w_gruntfile(motyw):
    assert (SCSS / f"{motyw}.scss").exists()
    sciezka = KORZEN / "Gruntfile.js"
    if not sciezka.exists():
        pytest.skip("Brak Gruntfile.js (obraz testowy w CI) — sprawdzane lokalnie.")
    gruntfile = sciezka.read_text()
    assert f"'src/bpp/static/scss/{motyw}.css'" in gruntfile


def _skompilowany(motyw):
    sciezka = finders.find(f"scss/{motyw}.css")
    if sciezka is None:
        pytest.fail(f"Brak scss/{motyw}.css — uruchom `make assets` / `grunt build`.")
    return Path(sciezka).read_text()


def test_auto_ciemny_wg_systemu_albo_przelacznika():
    """app-blue-auto: ciemny wg systemu, chyba że wybrano „Jasny”
    (przełącznik na pasku), oraz wymuszony „Ciemny” bez warunku na system."""
    css = _skompilowany("app-blue-auto")
    assert re.search(
        r"@media screen and \(prefers-color-scheme:\s*dark\)\s*\{\s*"
        r'html:where\(:not\(\[data-tryb-kolorow="?jasny"?\]\)\)\s*\{'
        r"\s*color-scheme:\s*dark",
        css,
    )
    assert re.search(
        r'@media screen\s*\{\s*html:where\(\[data-tryb-kolorow="?ciemny"?\]\)\s*\{'
        r"\s*color-scheme:\s*dark",
        css,
    )


def test_ciemny_zawsze_ciemny_ale_nie_na_wydruku():
    css = _skompilowany("app-blue-ciemny")
    assert "--tc-tlo" in css
    # (Foundation ma własne `prefers-color-scheme` w klasach widoczności —
    # sprawdzamy tylko, że NASZ blok nie jest od niego zależny.)
    assert not re.search(r"prefers-color-scheme:\s*dark\)\s*\{\s*html\s*\{", css)
    # Ciemne reguły siedzą w @media screen — wydruk zostaje jasny.
    assert re.search(r"@media screen\s*\{\s*html\s*\{\s*color-scheme:\s*dark", css)


def test_jasny_app_blue_bez_trybu_ciemnego():
    css = _skompilowany("app-blue")
    assert "--tc-tlo" not in css
    assert not re.search(r"html\s*\{\s*color-scheme:\s*dark", css)


def test_kafle_strony_glownej_bez_bialego_hover_w_szablonie():
    """Hover kafli był w <style> szablonu z `#fff !important` — motyw nie
    mógł go nadpisać (biały kwadrat w trybie ciemnym)."""
    szablon = (
        KORZEN / "src" / "bpp" / "templates" / "browse" / "uczelnia.html"
    ).read_text()
    assert ".browse-tile:hover" not in szablon


RE_ZMIENNA = re.compile(r"var\((--bpp-(?:tlo|tekst|ramka|akcent)[a-z0-9-]*),")


def _uzyte_zmienne_kolorow():
    """Zmienne `--bpp-*` z kolorem zapasowym w szablonach i arkuszach modułów."""
    src = KORZEN / "src"
    pliki = [*src.glob("*/templates/**/*.html"), *src.glob("*/static/*/scss/*.scss")]
    pliki += [*SCSS.glob("*.scss")]
    uzyte = {}
    for plik in pliki:
        for nazwa in RE_ZMIENNA.findall(plik.read_text(errors="replace")):
            uzyte.setdefault(nazwa, plik.relative_to(src))
    return uzyte


def test_zmienne_kolorow_zdefiniowane_w_obu_trybach_ciemnych():
    """Style spoza CSS motywu (bloki <style>, arkusze modułów) używają
    `var(--bpp-*, kolor)`. Każdą taką zmienną muszą definiować oba
    mechanizmy trybu ciemnego — inaczej w ciemnym zostaje jasny kolor
    zapasowy (biała plama)."""
    uzyte = _uzyte_zmienne_kolorow()
    assert "--bpp-tlo-pow" in uzyte  # metryki, optymalizacja publikacji

    reczny = (SCSS / "_tryb-ciemny.scss").read_text()
    konfig = (
        KORZEN / "src" / "bpp" / "static" / "bpp" / "js" / "motyw-konfig.js"
    ).read_text()
    for nazwa, plik in uzyte.items():
        assert f"{nazwa}:" in reczny, f"{nazwa} ({plik}) brak w _tryb-ciemny.scss"
        assert f'"{nazwa}' in konfig, f"{nazwa} ({plik}) brak w motyw-konfig.js"


def test_metryki_bez_jasnego_hovera_ustawianego_z_js():
    """Hover wiersza metryk był stylem inline z JS (#f0f8ff) — omijał oba
    mechanizmy trybu ciemnego. Teraz jest w CSS motywu."""
    lista = (
        KORZEN
        / "src"
        / "ewaluacja_metryki"
        / "templates"
        / "ewaluacja_metryki"
        / "lista.html"
    ).read_text()
    assert "css('background-color'" not in lista
    assert "ewaluacja-metryki-kolory" in (SCSS / "common.scss").read_text()


@pytest.mark.parametrize("szablon", ["lista.html", "szczegoly.html", "statystyki.html"])
def test_wykresy_metryk_dolaczaja_kolory_motywu(szablon):
    """Plotly i circle-progress rysują stałymi kolorami (białe tło) — skrypt
    wykresy-motyw.js podmienia je na kolory z wyliczonego stylu strony."""
    tresc = (
        KORZEN
        / "src"
        / "ewaluacja_metryki"
        / "templates"
        / "ewaluacja_metryki"
        / szablon
    ).read_text()
    assert "ewaluacja_metryki/js/wykresy-motyw.js" in tresc
    assert finders.find("ewaluacja_metryki/js/wykresy-motyw.js")


def _js_audytu():
    from bpp.tests.tryb_ciemny_audyt_js import JS_AUDYT

    return JS_AUDYT


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("sciezka", ["/", "/bpp/autorzy/", "/accounts/login/"])
def test_tryb_ciemny_bez_bialych_plam(channels_live_server, page, uczelnia, sciezka):
    """W app-blue-ciemny żaden duży element nie ma jasnego tła."""
    from model_bakery import baker

    from bpp.models import Autor

    uczelnia.theme_name = "app-blue-ciemny"
    uczelnia.save()
    baker.make(Autor, nazwisko="Ciemny", imiona="Test")

    page.emulate_media(color_scheme="dark")
    page.goto(channels_live_server.url + sciezka)
    page.wait_for_load_state("networkidle")
    wynik = page.evaluate(_js_audytu(), [0.8, 40])
    assert wynik["plamy"] == []


# --- Przełącznik trybu kolorów (top_bar.html) ------------------------------


@pytest.mark.parametrize(
    "motyw,oczekiwany",
    [("app-blue-auto", True), ("app-blue", False), ("app-blue-ciemny", False)],
)
def test_przelacznik_tylko_przy_motywie_z_dwiema_wersjami(motyw, oczekiwany):
    from bpp.context_processors.config import przelacznik_trybu_kolorow

    assert przelacznik_trybu_kolorow(motyw, None, False, None) is oczekiwany


def test_przelacznik_ukryty_w_podgladzie_i_przymiarce():
    from bpp.context_processors.config import przelacznik_trybu_kolorow

    assert not przelacznik_trybu_kolorow("app-blue-auto", None, True, None)
    assert not przelacznik_trybu_kolorow("app-blue-auto", None, False, "abc")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "tryb,oczekiwany", [("automatyczny", True), ("ciemny", False), ("jasny", False)]
)
def test_przelacznik_przy_motywie_z_konfiguratora(uczelnia, tryb, oczekiwany):
    from bpp.context_processors.config import przelacznik_trybu_kolorow
    from bpp.models import MOTYW_WLASNY, MotywWlasny

    MotywWlasny.objects.create(
        uczelnia=uczelnia, konfig={"wersja": 1, "tryb_kolorow": tryb}, css="a{}"
    )
    assert przelacznik_trybu_kolorow(MOTYW_WLASNY, uczelnia, False, None) is oczekiwany


@pytest.mark.django_db
@pytest.mark.parametrize("motyw,jest", [("app-blue-auto", True), ("app-blue", False)])
def test_przycisk_i_skrypt_w_head_tylko_z_flaga(client, uczelnia, motyw, jest):
    uczelnia.theme_name = motyw
    uczelnia.save()
    tresc = client.get("/").content.decode()
    assert ('data-ustaw-tryb-kolorow="ciemny"' in tresc) is jest
    assert ('localStorage.getItem("bpp-tryb-kolorow")' in tresc) is jest
    if jest:
        # Skrypt ustawiający atrybut stoi PRZED arkuszami stylów.
        assert tresc.index("bpp-tryb-kolorow") < tresc.index('rel="stylesheet"')


@pytest.mark.django_db(transaction=True)
def test_przelacznik_wybor_przezywa_przeladowanie(channels_live_server, page, uczelnia):
    """Jasny system + „Ciemny” → ciemno, także po przeładowaniu; ciemny system
    + „Jasny” → jasno."""
    uczelnia.theme_name = "app-blue-auto"
    uczelnia.save()

    def tlo_strony():
        return page.evaluate(
            "getComputedStyle(document.documentElement).backgroundColor"
        )

    page.emulate_media(color_scheme="light")
    page.goto(channels_live_server.url + "/")
    page.wait_for_load_state("networkidle")
    jasne = tlo_strony()
    page.evaluate("window.bppTrybKolorow.ustaw('ciemny')")
    assert tlo_strony() != jasne
    page.reload()
    page.wait_for_load_state("networkidle")
    assert page.evaluate("document.documentElement.dataset.trybKolorow") == "ciemny"
    assert tlo_strony() != jasne
    wynik = page.evaluate(_js_audytu(), [0.8, 40])
    assert wynik["plamy"] == []

    page.emulate_media(color_scheme="dark")
    page.locator('[data-ustaw-tryb-kolorow="jasny"]').dispatch_event("click")
    assert page.evaluate("localStorage.getItem('bpp-tryb-kolorow')") == "jasny"
    assert tlo_strony() == jasne
