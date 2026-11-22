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


MOTYWY_PODSTAWOWE = ["app-blue", "app-green", "app-orange", "app-vizja", "app-mwsl"]
MOTYWY_PODSTAWOWE += ["app-uafm"]


@pytest.mark.parametrize("motyw", [f"{m}-ciemny" for m in MOTYWY_PODSTAWOWE])
def test_ciemny_domyslnie_ciemny_ale_nie_na_wydruku(motyw):
    """*-ciemny: ciemny bez warunku na system; „Jasny” z pigułki go wyłącza."""
    css = _skompilowany(motyw)
    assert "--tc-tlo" in css
    # (Foundation ma własne `prefers-color-scheme` w klasach widoczności —
    # sprawdzamy tylko, że NASZ blok nie jest od niego zależny.)
    assert not re.search(
        r"prefers-color-scheme:\s*dark\)\s*\{\s*html(:where|\s*\{)", css
    )
    # Ciemne reguły siedzą w @media screen — wydruk zostaje jasny.
    assert re.search(
        r'@media screen\s*\{\s*html:where\(:not\(\[data-tryb-kolorow="?jasny"?\]\)\)'
        r"\s*\{\s*color-scheme:\s*dark",
        css,
    )


@pytest.mark.parametrize("motyw", MOTYWY_PODSTAWOWE)
def test_zwykly_motyw_ciemny_tylko_z_pigulki(motyw):
    """Zwykły motyw: domyślnie jasny NIEZALEŻNIE od systemu; ciemne reguły
    tylko pod wyborem „Ciemny” (pigułka), w @media screen."""
    css = _skompilowany(motyw)
    assert re.search(
        r'@media screen\s*\{\s*html:where\(\[data-tryb-kolorow="?ciemny"?\]\)\s*\{'
        r"\s*color-scheme:\s*dark",
        css,
    )
    assert not re.search(
        r"prefers-color-scheme:\s*dark\)\s*\{\s*html(:where|\s*\{)", css
    )
    assert ':not([data-tryb-kolorow="jasny"])' not in css
    assert not re.search(r"(^|[{}])html\s*\{\s*color-scheme:\s*dark", css)


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
    [
        ("app-blue-auto", "auto"),
        ("app-blue", "jasny"),
        ("app-blue-ciemny", "ciemny"),
        ("app-green", "jasny"),
        ("app-uafm-auto", "auto"),
        ("app-mwsl-ciemny", "ciemny"),
    ],
)
def test_tryb_domyslny_motywu(motyw, oczekiwany):
    from bpp.context_processors.config import tryb_kolorow_domyslny

    assert tryb_kolorow_domyslny(motyw, None) == oczekiwany


def test_przelacznik_zawsze_poza_podgladem_i_przymiarka():
    from bpp.context_processors.config import przelacznik_trybu_kolorow

    assert przelacznik_trybu_kolorow(False, None)
    assert not przelacznik_trybu_kolorow(True, None)
    assert not przelacznik_trybu_kolorow(False, "abc")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "tryb,oczekiwany",
    [("automatyczny", "auto"), ("ciemny", "ciemny"), ("jasny", "jasny")],
)
def test_tryb_domyslny_motywu_z_konfiguratora(uczelnia, tryb, oczekiwany):
    from bpp.context_processors.config import tryb_kolorow_domyslny
    from bpp.models import MOTYW_WLASNY, MotywWlasny

    MotywWlasny.objects.create(
        uczelnia=uczelnia, konfig={"wersja": 1, "tryb_kolorow": tryb}, css="a{}"
    )
    assert tryb_kolorow_domyslny(MOTYW_WLASNY, uczelnia) == oczekiwany


def test_tryb_domyslny_motywu_z_pliku_konfiguracji(tmp_path):
    from django_bpp.motywy_z_konfiguracji import tryb_kolorow_motywu

    (tmp_path / "noc.json").write_text('{"nazwa": "noc", "tryb_kolorow": "ciemny"}')
    (tmp_path / "dzien.json").write_text('{"nazwa": "dzien"}')
    assert tryb_kolorow_motywu("app-noc", tmp_path) == "ciemny"
    assert tryb_kolorow_motywu("app-dzien", tmp_path) == "jasny"
    assert tryb_kolorow_motywu("app-blue", tmp_path) is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "motyw,domyslny",
    [("app-blue-auto", "auto"), ("app-blue", "jasny"), ("app-blue-ciemny", "ciemny")],
)
def test_pigulka_i_skrypt_w_head_przy_kazdym_motywie(client, uczelnia, motyw, domyslny):
    uczelnia.theme_name = motyw
    uczelnia.save()
    tresc = client.get("/").content.decode()
    # Dwie pigułki: pasek tytułowy (telefon) i pasek menu (komputer).
    assert tresc.count('class="dropdown menu bpp-pigulka"') == 2
    assert 'role="radiogroup" aria-label="Tryb kolorów"' in tresc
    assert 'localStorage.getItem("bpp-tryb-kolorow")' in tresc
    assert f'data-tryb-domyslny="{domyslny}"' in tresc
    # Stara pozycja menu „kolory” z listą zniknęła.
    assert "bpp-tryb-kolorow__przycisk" not in tresc
    # Skrypt ustawiający atrybut stoi PRZED arkuszami stylów.
    assert tresc.index("bpp-tryb-kolorow") < tresc.index('rel="stylesheet"')


def _polowka(page, tryb):
    """Widoczna połówka pigułki (komputer: pasek menu; telefon: tytułowy)."""
    return page.locator(f'.bpp-pigulka:visible [data-ustaw-tryb-kolorow="{tryb}"]')


def _tlo_strony(page):
    return page.evaluate("getComputedStyle(document.documentElement).backgroundColor")


def _wybor(page):
    return page.evaluate(
        "[document.documentElement.dataset.trybKolorow || null,"
        " localStorage.getItem('bpp-tryb-kolorow')]"
    )


def _suwak_przesuniety(page):
    """Czy suwak podświetlenia widocznej pigułki stoi pod księżycem —
    liczone z samego CSS."""
    return page.evaluate(
        "getComputedStyle([...document.querySelectorAll('.bpp-pigulka__tor')]"
        ".find((e) => e.offsetParent)).transform !== 'none'"
    )


@pytest.mark.django_db(transaction=True)
def test_pigulka_klik_przeladowanie_i_powrot_do_auto(
    channels_live_server, page, uczelnia
):
    """Jasny system: księżyc → ciemno (także po przeładowaniu); klik
    w podświetlony księżyc → z powrotem automatyczny (jasno)."""
    uczelnia.theme_name = "app-blue-auto"
    uczelnia.save()

    page.emulate_media(color_scheme="light")
    page.goto(channels_live_server.url + "/")
    page.wait_for_load_state("networkidle")
    jasne = _tlo_strony(page)
    assert _polowka(page, "jasny").get_attribute("aria-checked") == "true"
    assert _polowka(page, "ciemny").get_attribute("aria-checked") == "false"

    _polowka(page, "ciemny").click()
    assert _wybor(page) == ["ciemny", "ciemny"]
    assert _tlo_strony(page) != jasne

    page.reload()
    page.wait_for_load_state("networkidle")
    assert _wybor(page) == ["ciemny", "ciemny"]
    assert _tlo_strony(page) != jasne
    ksiezyc = _polowka(page, "ciemny")
    assert ksiezyc.get_attribute("aria-checked") == "true"
    assert "wrócić do ustawień systemu" in ksiezyc.get_attribute("aria-label")
    wynik = page.evaluate(_js_audytu(), [0.8, 40])
    assert wynik["plamy"] == []

    ksiezyc.click()  # wybrany ręcznie → automatyczny
    assert _wybor(page) == [None, None]
    assert _tlo_strony(page) == jasne
    assert _polowka(page, "jasny").get_attribute("aria-checked") == "true"


@pytest.mark.django_db(transaction=True)
def test_pigulka_ciemny_system_i_klawiatura(channels_live_server, page, uczelnia):
    """Ciemny system: suwak pod księżycem z CSS; strzałka wymusza jasny,
    Spacja na wybranej połówce wraca do automatycznego."""
    uczelnia.theme_name = "app-blue-auto"
    uczelnia.save()

    # Bez animacji przesunięcia (prefers-reduced-motion) — suwak od razu
    # na miejscu, bez stanów pośrednich.
    page.emulate_media(color_scheme="dark", reduced_motion="reduce")
    page.goto(channels_live_server.url + "/")
    page.wait_for_load_state("networkidle")
    ciemne = _tlo_strony(page)
    assert _suwak_przesuniety(page)

    _polowka(page, "ciemny").focus()
    page.keyboard.press("ArrowLeft")
    assert _wybor(page) == ["jasny", "jasny"]
    assert _tlo_strony(page) != ciemne
    assert not _suwak_przesuniety(page)
    aktywny = "document.activeElement.getAttribute('data-ustaw-tryb-kolorow')"
    assert page.evaluate(aktywny) == "jasny"
    assert _polowka(page, "jasny").get_attribute("tabindex") == "0"
    assert _polowka(page, "ciemny").get_attribute("tabindex") == "-1"

    page.keyboard.press(" ")
    assert _wybor(page) == [None, None]
    assert _tlo_strony(page) == ciemne
    assert _suwak_przesuniety(page)


@pytest.mark.django_db(transaction=True)
def test_pigulka_na_telefonie_bez_otwierania_menu(channels_live_server, page, uczelnia):
    """Telefon: pigułka na pasku tytułowym obok ikony menu, menu zamknięte."""
    uczelnia.theme_name = "app-blue-auto"
    uczelnia.save()

    page.set_viewport_size({"width": 390, "height": 800})
    page.emulate_media(color_scheme="light")
    page.goto(channels_live_server.url + "/")
    page.wait_for_load_state("networkidle")

    pigulka = page.locator(".title-bar .bpp-pigulka")
    assert pigulka.is_visible()
    assert not page.locator(".top-bar .bpp-pigulka").is_visible()
    ikona = page.locator(".title-bar .bpp-ikona-menu").bounding_box()
    ramka = pigulka.bounding_box()
    assert ramka["x"] > ikona["x"] + ikona["width"]
    assert ramka["x"] + ramka["width"] < 390 * 0.6  # z dala od UserWay

    _polowka(page, "ciemny").click()
    assert _wybor(page) == ["ciemny", "ciemny"]


@pytest.mark.django_db(transaction=True)
def test_zwykly_motyw_jasny_przy_ciemnym_systemie_ciemny_z_pigulki(
    channels_live_server, page, uczelnia
):
    """Zwykły motyw (app-green): ciemny system bez wyboru → jasno jak dotąd;
    ☾ → ciemno; ☀ → z powrotem domyślny (bez wpisu w localStorage)."""
    uczelnia.theme_name = "app-green"
    uczelnia.save()

    page.emulate_media(color_scheme="light", reduced_motion="reduce")
    page.goto(channels_live_server.url + "/")
    page.wait_for_load_state("networkidle")
    jasne_przy_jasnym = _tlo_strony(page)

    page.emulate_media(color_scheme="dark", reduced_motion="reduce")
    page.reload()
    page.wait_for_load_state("networkidle")
    assert _tlo_strony(page) == jasne_przy_jasnym
    assert not _suwak_przesuniety(page)
    slonce = _polowka(page, "jasny")
    assert slonce.get_attribute("aria-checked") == "true"
    assert "domyślny wygląd strony" in slonce.get_attribute("aria-label")

    _polowka(page, "ciemny").click()
    assert _wybor(page) == ["ciemny", "ciemny"]
    assert _tlo_strony(page) != jasne_przy_jasnym
    assert _suwak_przesuniety(page)
    page.reload()
    page.wait_for_load_state("networkidle")
    assert _suwak_przesuniety(page)
    wynik = page.evaluate(_js_audytu(), [0.8, 40])
    assert wynik["plamy"] == []

    _polowka(page, "jasny").click()
    assert _wybor(page) == [None, None]
    assert _tlo_strony(page) == jasne_przy_jasnym


@pytest.mark.django_db(transaction=True)
def test_motyw_ciemny_pigulka_wymusza_jasny(channels_live_server, page, uczelnia):
    """*-ciemny: bez wyboru ciemno (także przy jasnym systemie); ☀ → jasno;
    ponowny klik ☀ → z powrotem domyślny ciemny."""
    uczelnia.theme_name = "app-blue-ciemny"
    uczelnia.save()

    page.emulate_media(color_scheme="light", reduced_motion="reduce")
    page.goto(channels_live_server.url + "/")
    page.wait_for_load_state("networkidle")
    ciemne = _tlo_strony(page)
    assert _suwak_przesuniety(page)

    _polowka(page, "jasny").click()
    assert _wybor(page) == ["jasny", "jasny"]
    assert _tlo_strony(page) != ciemne
    assert not _suwak_przesuniety(page)

    _polowka(page, "jasny").click()
    assert _wybor(page) == [None, None]
    assert _tlo_strony(page) == ciemne
