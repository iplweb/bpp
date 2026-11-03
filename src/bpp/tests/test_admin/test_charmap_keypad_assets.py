"""Klawiatura znaków specjalnych (kbw-keypad) ładuje się TYLKO na stronach
admina, które mają pola ``.charmap`` — nie globalnie na każdej stronie.

Testy sprawdzają wyrenderowany HTML (nie fizyczną obecność plików), więc
nie zależą od ``node_modules`` ani zebranych statyków.
"""

import re

import pytest
from django.urls import reverse

from bpp.admin.helpers.widgets import (
    CHARMAP_SINGLE_LINE,
    NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW,
)

KEYPAD_JS = "kbw-keypad/dist/js/jquery.keypad.js"
KEYPAD_CSS = "kbw-keypad/dist/css/jquery.keypad.css"
KEYPAD_INIT = "bpp/js/charmap-keypad.js"


def _static_re(path):
    """Wzorzec ścieżki statyku, także z hashem ManifestStaticFilesStorage
    (``jquery.keypad.350ad5374742.js``)."""
    base, ext = path.rsplit(".", 1)
    return re.compile(re.escape(base) + r"(\.[0-9a-f]{12})?\." + ext)


def _pozycja(html, path):
    m = _static_re(path).search(html)
    assert m, f"brak {path} w HTML strony"
    return m.start()


@pytest.mark.parametrize(
    "widget",
    [
        CHARMAP_SINGLE_LINE,
        NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW[
            next(iter(NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW))
        ]["widget"],
    ],
)
def test_widget_charmap_deklaruje_media_keypada(widget):
    assert "charmap" in widget.attrs["class"]
    media = str(widget.media)
    _pozycja(media, KEYPAD_CSS)
    assert _pozycja(media, KEYPAD_JS) < _pozycja(media, KEYPAD_INIT)


@pytest.mark.parametrize(
    "url",
    [
        "admin:index",
        "admin:bpp_wydawnictwo_ciagle_changelist",
        "admin:bpp_jednostka_add",
    ],
)
def test_strona_bez_pol_charmap_nie_laduje_keypada(admin_app, uczelnia, url):
    html = admin_app.get(reverse(url)).content.decode("utf-8")
    assert 'class="charmap"' not in html
    assert "kbw-keypad" not in html
    assert KEYPAD_INIT not in html
    assert ".keypad(" not in html


@pytest.mark.parametrize(
    "url",
    [
        "admin:bpp_wydawnictwo_ciagle_add",
        "admin:bpp_wydawnictwo_zwarte_add",
        "admin:bpp_praca_doktorska_add",
        "admin:bpp_autor_add",
        "admin:bpp_zrodlo_add",
    ],
)
def test_strona_z_polami_charmap_laduje_keypad(admin_app, uczelnia, url):
    html = admin_app.get(reverse(url)).content.decode("utf-8")
    assert 'class="charmap"' in html
    _pozycja(html, KEYPAD_CSS)
    jquery_init = _pozycja(html, "admin/js/jquery.init.js")
    plugin = _pozycja(html, "kbw-keypad/dist/js/jquery.plugin.min.js")
    keypad = _pozycja(html, KEYPAD_JS)
    init = _pozycja(html, KEYPAD_INIT)
    # Wtyczki muszą się załadować PO jquery.init.js Django (dopiero wtedy
    # globalny jQuery to znów grp.jQuery), a inicjalizacja PO wtyczkach.
    assert jquery_init < plugin < keypad < init
