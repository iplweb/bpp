"""Rejestr motywów: klucz CLI → Theme."""

from __future__ import annotations

from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.realistyczny import REALISTYCZNY

THEMES: dict[str, Theme] = {t.key: t for t in (REALISTYCZNY,)}


def get_theme(key: str) -> Theme:
    try:
        return THEMES[key]
    except KeyError:
        raise ValueError(
            f"Nieznany motyw '{key}'. Dostępne: {sorted(THEMES)}"
        ) from None
