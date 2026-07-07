"""Testy E2E widgetu osadzania publikacji (loader bpp-publikacje.js).

Loader ładowany jest z ``/static/embed/bpp-publikacje.js`` (serwowany przez
``ASGIStaticFilesHandler`` w live-serverze). Strona-host jest budowana przez
``set_content`` — symuluje zewnętrzną witrynę osadzającą widget cross-origin.
"""

import pytest
from model_bakery import baker
from playwright.sync_api import Page

from bpp.models import Autor, Rekord, Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor


def _strona_z_widgetem(page: Page, base_url: str, script_attrs: str) -> None:
    """Załaduj minimalną stronę-hosta z tagiem loadera."""
    page.set_content(
        "<!doctype html><html><head></head><body>"
        f'<script src="{base_url}/static/embed/bpp-publikacje.js" '
        f'data-serwer="{base_url}" {script_attrs}></script>'
        "</body></html>"
    )


def test_embed_widget_renderuje_liste(channels_live_server, page: Page, transactional_db):
    """Widget pobiera publikacje autora z API i renderuje listę pozycji."""
    autor = baker.make(Autor, nazwisko="Widgetowy", imiona="Wiktor")
    for i in range(3):
        pub = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=f"Praca widget {i}")
        baker.make(Wydawnictwo_Ciagle_Autor, rekord=pub, autor=autor)
    Rekord.objects.full_refresh()

    _strona_z_widgetem(
        page, channels_live_server.url, f'data-autor="{autor.slug}"'
    )

    page.wait_for_selector(".bpp-publikacje__item", timeout=15000)
    assert page.locator(".bpp-publikacje__item").count() == 3
    # Stopka z linkiem do pełnego profilu
    assert page.locator(".bpp-publikacje__stopka").count() == 1


def test_embed_widget_pusta_lista(channels_live_server, page: Page, transactional_db):
    """Autor bez publikacji → komunikat o braku, bez wywrotki."""
    autor = baker.make(Autor, nazwisko="Bezprac", imiona="Bartosz")
    Rekord.objects.full_refresh()

    _strona_z_widgetem(page, channels_live_server.url, f'data-autor="{autor.slug}"')

    page.wait_for_selector(".bpp-publikacje__empty", timeout=15000)
    assert page.locator(".bpp-publikacje__item").count() == 0


def test_embed_widget_sanityzuje_xss(channels_live_server, page: Page, transactional_db):
    """Sanitizer loadera usuwa niebezpieczny HTML (allowlist), zachowuje
    tagi formatujące, i nigdy nie wykonuje wstrzykniętego kodu."""
    autor = baker.make(Autor, nazwisko="Pusty", imiona="Piotr")
    Rekord.objects.full_refresh()
    _strona_z_widgetem(page, channels_live_server.url, f'data-autor="{autor.slug}"')

    page.wait_for_function("() => typeof window.__bppPublikacjeSanitize === 'function'")

    wynik = page.evaluate(
        r"""() => window.__bppPublikacjeSanitize(
            '<img src=x onerror="window.__pwned=1">Ala <b>ma</b> <i>kota</i>'
            + '<script>window.__pwned=1<\/script>'
        )"""
    )

    assert "onerror" not in wynik
    assert "<img" not in wynik
    assert "<script" not in wynik.lower()
    # tagi formatujące zachowane, tekst zachowany
    assert "<b>ma</b>" in wynik
    assert "<i>kota</i>" in wynik
    assert "Ala" in wynik
    # kod nigdy się nie wykonał
    assert not page.evaluate("() => window.__pwned")


@pytest.mark.parametrize("styl", ["lista", "tabela"])
def test_embed_widget_styl(channels_live_server, page: Page, transactional_db, styl):
    """Wariant data-styl wybiera render listy albo tabeli."""
    autor = baker.make(Autor, nazwisko="Stylowy", imiona="Stanisław")
    pub = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca stylowa")
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=pub, autor=autor)
    Rekord.objects.full_refresh()

    _strona_z_widgetem(
        page, channels_live_server.url, f'data-autor="{autor.slug}" data-styl="{styl}"'
    )

    selektor = (
        ".bpp-publikacje__tabela" if styl == "tabela" else ".bpp-publikacje__lista"
    )
    page.wait_for_selector(selektor, timeout=15000)
    assert page.locator(selektor).count() == 1
