"""Ekstrakcja danych z citation_* meta tagów (Highwire Press)."""

from bs4 import BeautifulSoup

from .parsers import (
    _clean_doi,
    _get_all_meta,
    _get_meta,
    _parse_author_name,
    _parse_year,
)


def _extract_citation_meta(soup: BeautifulSoup) -> dict:
    """Wyciągnij dane z citation_* meta tagów."""
    result = {}

    title = _get_meta(soup, "citation_title")
    if title:
        result["title"] = title

    authors_raw = _get_all_meta(soup, "citation_author")
    if authors_raw:
        result["authors"] = [_parse_author_name(a) for a in authors_raw]

    doi = _get_meta(soup, "citation_doi")
    if doi:
        result["doi"] = _clean_doi(doi)

    _add_simple_fields(result, soup)
    _add_pages_field(result, soup)
    _add_date_field(result, soup)
    _add_keywords_field(result, soup)

    return result


def _add_simple_fields(result: dict, soup: BeautifulSoup) -> None:
    """Dodaj proste pola z citation_* meta tagów."""
    fields = {
        "citation_journal_title": "source_title",
        "citation_journal_abbrev": "source_abbreviation",
        "citation_issn": "issn",
        "citation_volume": "volume",
        "citation_issue": "issue",
        "citation_publisher": "publisher",
        "citation_language": "language",
        "citation_isbn": "isbn",
    }
    for meta_name, result_key in fields.items():
        value = _get_meta(soup, meta_name)
        if value:
            result[result_key] = value


def _add_pages_field(result: dict, soup: BeautifulSoup) -> None:
    """Dodaj pole pages z citation_firstpage/lastpage."""
    firstpage = _get_meta(soup, "citation_firstpage")
    lastpage = _get_meta(soup, "citation_lastpage")
    if firstpage:
        if lastpage:
            result["pages"] = f"{firstpage}-{lastpage}"
        else:
            result["pages"] = firstpage


def _add_date_field(result: dict, soup: BeautifulSoup) -> None:
    """Dodaj pole year z citation_date."""
    date = _get_meta(soup, "citation_date") or _get_meta(
        soup, "citation_publication_date"
    )
    if date:
        year = _parse_year(date)
        if year:
            result["year"] = year


def _add_keywords_field(result: dict, soup: BeautifulSoup) -> None:
    """Dodaj pole keywords z citation_keywords."""
    keywords = _get_all_meta(soup, "citation_keywords")
    if keywords:
        result["keywords"] = keywords
