"""Rejestr motywów: klucz CLI → Theme."""

from __future__ import annotations

from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.disney import DISNEY
from bpp.demo_data.themes.harry_potter import HARRY_POTTER
from bpp.demo_data.themes.lem import LEM
from bpp.demo_data.themes.realistyczny import REALISTYCZNY
from bpp.demo_data.themes.wiedzmin import WIEDZMIN

THEMES: dict[str, Theme] = {
    t.key: t for t in (REALISTYCZNY, LEM, WIEDZMIN, HARRY_POTTER, DISNEY)
}


def get_theme(key: str) -> Theme:
    try:
        return THEMES[key]
    except KeyError:
        raise ValueError(
            f"Nieznany motyw '{key}'. Dostępne: {sorted(THEMES)}"
        ) from None
