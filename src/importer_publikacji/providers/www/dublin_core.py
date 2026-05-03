"""Ekstrakcja danych z meta tagów Dublin Core (DC.*)."""

from bs4 import BeautifulSoup

from .parsers import (
    _clean_doi,
    _get_all_meta,
    _get_meta,
    _parse_author_name,
    _parse_year,
)


def _extract_dublin_core(soup: BeautifulSoup) -> dict:
    """Wyciągnij dane z Dublin Core meta tagów."""
    result = {}

    title = _get_meta(soup, "DC.title")
    if title:
        result["title"] = title

    creators = _get_all_meta(soup, "DC.creator")
    if creators:
        result["authors"] = [_parse_author_name(c) for c in creators]

    date = _get_meta(soup, "DC.date")
    if date:
        year = _parse_year(date)
        if year:
            result["year"] = year

    _extract_dc_doi(result, soup)
    _extract_dc_simple_fields(result, soup)

    return result


def _extract_dc_doi(result: dict, soup: BeautifulSoup) -> None:
    """Wyciągnij DOI z DC.identifier meta tagów."""
    identifiers = _get_all_meta(soup, "DC.identifier")
    for ident in identifiers:
        if "10." in ident:
            result["doi"] = _clean_doi(ident)
            break


def _extract_dc_simple_fields(result: dict, soup: BeautifulSoup) -> None:
    """Dodaj proste pola z Dublin Core meta tagów."""
    dc_fields = {
        "DC.source": "source_title",
        "DC.publisher": "publisher",
        "DC.language": "language",
        "DC.description": "abstract",
    }
    for meta_name, result_key in dc_fields.items():
        value = _get_meta(soup, meta_name)
        if value:
            result[result_key] = value
