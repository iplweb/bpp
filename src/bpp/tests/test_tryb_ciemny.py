"""Ciemne warianty motywów (_tryb-ciemny.scss): app-blue-auto, app-blue-ciemny.

Patrz docs/deweloper/budowanie-css.md, sekcja „Tryb ciemny”.
"""

import importlib.util
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.staticfiles import finders

KORZEN = Path(__file__).resolve().parents[3]
SCSS = KORZEN / "src" / "bpp" / "static" / "scss"

CIEMNE_WARIANTY = ["app-blue-auto", "app-blue-ciemny"]


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
    gruntfile = (KORZEN / "Gruntfile.js").read_text()
    assert f"'src/bpp/static/scss/{motyw}.css'" in gruntfile


def _skompilowany(motyw):
    sciezka = finders.find(f"scss/{motyw}.css")
    if sciezka is None:
        pytest.fail(f"Brak scss/{motyw}.css — uruchom `make assets` / `grunt build`.")
    return Path(sciezka).read_text()


def test_auto_wlacza_ciemny_tylko_przy_preferencji_systemu():
    css = _skompilowany("app-blue-auto")
    assert re.search(
        r"@media screen and \(prefers-color-scheme:\s*dark\)\s*\{\s*html\s*\{"
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


def _js_audytu():
    sciezka = KORZEN / "bin" / "tryb-ciemny-audyt.py"
    spec = importlib.util.spec_from_file_location("tryb_ciemny_audyt", sciezka)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul.JS_AUDYT


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
