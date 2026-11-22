import re
from pathlib import Path

import pytest
from django.template import Context, Template
from django.urls import reverse

from bpp import porady
from bpp.porady import DOKUMENTACJA_URL, PORADY, Porada, wersja_porad

KATALOG_REPO = Path(__file__).resolve().parents[3]
KATALOG_DOCS = KATALOG_REPO / "docs"


def _wyrenderuj_pasek():
    return Template("{% load porady %}{% pasek_porad %}").render(Context({}))


def test_pasek_porad_renderuje_wszystkie_porady():
    html = _wyrenderuj_pasek()

    assert "Porady BPP:" in html
    for porada in PORADY:
        assert porada.url in html
    # Bez JS widać pierwszą poradę, pozostałe czekają ukryte na rotację.
    assert html.count('class="tip-item"') == len(PORADY)
    assert html.count('class="tip-item" hidden') == len(PORADY) - 1


def test_pasek_porad_przycisk_zamkniecia():
    html = _wyrenderuj_pasek()

    assert re.search(
        r'<button type="button" class="tips-close"\s+'
        r'aria-label="Zamknij porady"',
        html,
    )
    assert f'data-wersja-porad="{wersja_porad()}"' in html
    assert "localStorage" in html


def test_pasek_porad_linki_w_nowym_oknie():
    html = _wyrenderuj_pasek()

    linki = re.findall(r"<a [^>]*>", html)
    assert len(linki) == len(PORADY)
    for link in linki:
        assert 'target="_blank"' in link
        assert 'rel="noopener"' in link
        assert f'href="{DOKUMENTACJA_URL}' in link


def test_porady_linkuja_do_dokumentacji_ze_spisu():
    """Każda porada wskazuje na istniejącą stronę dokumentacji (i kotwicę),
    obecną w nawigacji mkdocs."""
    if not KATALOG_DOCS.is_dir():
        # Obraz test-runnera na CI nie zawiera docs/ (.dockerignore).
        pytest.skip("brak katalogu docs/ w tym środowisku")

    mkdocs = (KATALOG_REPO / "mkdocs.yml").read_text()
    assert f"site_url: {DOKUMENTACJA_URL}" in mkdocs

    for porada in PORADY:
        sciezka, _, kotwica = porada.dokumentacja.partition("#")
        assert sciezka.endswith("/"), porada.dokumentacja
        plik_md = sciezka.rstrip("/") + ".md"
        assert (KATALOG_DOCS / plik_md).is_file(), plik_md
        assert f": {plik_md}" in mkdocs, f"{plik_md} poza nawigacją mkdocs"
        if kotwica:
            assert "{#" + kotwica + "}" in (KATALOG_DOCS / plik_md).read_text()


def test_wersja_porad_zmienia_sie_ze_zmiana_tresci(monkeypatch):
    wersja_przed = wersja_porad()

    monkeypatch.setattr(
        porady, "PORADY", PORADY + (Porada("Nowa porada.", "uzytkownik/"),)
    )
    wersja_porad.cache_clear()
    try:
        assert wersja_porad() != wersja_przed
    finally:
        monkeypatch.undo()
        wersja_porad.cache_clear()

    assert wersja_porad() == wersja_przed


@pytest.mark.django_db
def test_strona_glowna_pokazuje_pasek_porad(client, uczelnia):
    res = client.get(reverse("root"))

    assert res.status_code == 200
    tresc = res.content.decode()
    assert 'id="rotating-tips"' in tresc
    assert 'aria-label="Zamknij porady"' in tresc


@pytest.mark.django_db
def test_strona_uczelni_pokazuje_pasek_porad(client, uczelnia):
    res = client.get(reverse("bpp:browse_uczelnia", args=(uczelnia.slug,)))

    assert res.status_code == 200
    assert 'id="rotating-tips"' in res.content.decode()
