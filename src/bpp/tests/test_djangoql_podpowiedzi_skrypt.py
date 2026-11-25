"""Każde miejsce ładujące widżet podpowiedzi DjangoQL ładuje też skrypt,
który każe mu traktować podpowiadany tekst jako dane, a nie HTML."""

import re
from pathlib import Path

import pytest
from django.contrib import admin

from bpp.admin.helpers.djangoql import (
    SKRYPT_ESCAPOWANIA_PODPOWIEDZI,
    BppDjangoQLSearchMixin,
)

SRC = Path(__file__).resolve().parents[2]
WIDZET = "djangoql/js/completion.js"


def _szablony_z_widzetem():
    return sorted(
        p
        for p in SRC.rglob("templates/**/*.html")
        if WIDZET in p.read_text(encoding="utf-8")
    )


def test_sa_szablony_ladujace_widzet():
    # Bez tego test niżej przechodziłby „na pusto” po zmianie nazwy pliku.
    assert _szablony_z_widzetem()


@pytest.mark.parametrize(
    "szablon", _szablony_z_widzetem(), ids=lambda p: str(p.relative_to(SRC))
)
def test_szablon_laduje_skrypt_zaraz_po_widzecie(szablon):
    skrypty = re.findall(
        r"<script[^>]*\bsrc=\"\{% static '([^']+)' %\}\"",
        szablon.read_text(encoding="utf-8"),
    )
    assert WIDZET in skrypty
    pozycja = skrypty.index(WIDZET)
    assert skrypty[pozycja + 1 : pozycja + 2] == [SKRYPT_ESCAPOWANIA_PODPOWIEDZI]


def _adminy_z_wyszukiwarka_djangoql():
    return [
        model_admin
        for model_admin in admin.site._registry.values()
        if isinstance(model_admin, BppDjangoQLSearchMixin)
    ]


@pytest.mark.django_db
def test_adminy_laduja_skrypt_po_widzecie():
    adminy = _adminy_z_wyszukiwarka_djangoql()
    assert adminy
    for model_admin in adminy:
        skrypty = [str(js) for js in model_admin.media._js]
        widzet = next(i for i, js in enumerate(skrypty) if WIDZET in js)
        skrypt = next(
            i for i, js in enumerate(skrypty) if SKRYPT_ESCAPOWANIA_PODPOWIEDZI in js
        )
        assert widzet < skrypt, type(model_admin).__name__
