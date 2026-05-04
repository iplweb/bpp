"""Ekstrakcja danych z meta tagów OpenGraph (fallback ostatniej szansy)."""

from bs4 import BeautifulSoup

from .parsers import _get_meta_property


def _extract_opengraph(soup: BeautifulSoup) -> dict:
    """Wyciągnij dane z OpenGraph meta tagów (fallback)."""
    result = {}
    title = _get_meta_property(soup, "og:title")
    if title:
        result["title"] = title
    return result
