"""Ekstrakcja danych z bloków Schema.org JSON-LD osadzonych w HTML."""

import json

from bs4 import BeautifulSoup

from .parsers import _clean_doi, _parse_author_name, _parse_year


def _extract_schema_jsonld(soup: BeautifulSoup) -> dict:
    """Wyciągnij dane z Schema.org JSON-LD w HTML."""
    result = {}
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    for script in scripts:
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        items = data if isinstance(data, list) else [data]
        if _process_schema_items(items, result):
            break  # use first Article found

    return result


def _process_schema_items(items: list, result: dict) -> bool:
    """Przetwórz schemę JSON-LD i pobierz dane artykułu.

    Zwraca True jeśli znaleziono artykuł, False w przeciwnym razie.
    """
    for item in items:
        if not isinstance(item, dict):
            continue
        item_type = item.get("@type", "")
        if isinstance(item_type, list):
            type_str = " ".join(item_type)
        else:
            type_str = str(item_type)
        if "Article" not in type_str:
            continue

        _extract_schema_title(result, item)
        _extract_schema_authors(result, item)
        _extract_schema_doi(result, item)
        _extract_schema_date(result, item)
        _extract_schema_ispartof(result, item)
        _extract_schema_publisher(result, item)
        _extract_schema_volume_issue(result, item)
        _extract_schema_pages(result, item)

        return True  # Found article

    return False


def _extract_schema_title(result: dict, item: dict) -> None:
    """Wyciągnij tytuł."""
    headline = item.get("headline") or item.get("name")
    if headline and "title" not in result:
        result["title"] = headline


def _extract_schema_authors(result: dict, item: dict) -> None:
    """Wyciągnij autorów."""
    authors_data = item.get("author", [])
    if not isinstance(authors_data, list):
        authors_data = [authors_data]
    authors = []
    for a in authors_data:
        if isinstance(a, dict):
            name = a.get("name", "")
            family = a.get("familyName", "")
            given = a.get("givenName", "")
            if family or given:
                authors.append(
                    {
                        "family": family,
                        "given": given,
                    }
                )
            elif name:
                authors.append(_parse_author_name(name))
        elif isinstance(a, str) and a:
            authors.append(_parse_author_name(a))
    if authors and "authors" not in result:
        result["authors"] = authors


def _extract_schema_doi(result: dict, item: dict) -> None:
    """Wyciągnij DOI."""
    doi_val = item.get("doi") or item.get("sameAs", "")
    if isinstance(doi_val, str) and "doi" not in result:
        cleaned = _clean_doi(doi_val)
        if cleaned and "10." in cleaned:
            result["doi"] = cleaned


def _extract_schema_date(result: dict, item: dict) -> None:
    """Wyciągnij datę publikacji."""
    date_pub = item.get("datePublished") or item.get("dateCreated")
    if date_pub and "year" not in result:
        year = _parse_year(str(date_pub))
        if year:
            result["year"] = year


def _extract_schema_ispartof(result: dict, item: dict) -> None:
    """Wyciągnij informacje z isPartOf."""
    part_of = item.get("isPartOf")
    if isinstance(part_of, dict):
        jname = part_of.get("name")
        if jname and "source_title" not in result:
            result["source_title"] = jname
        jissn = part_of.get("issn")
        if jissn and "issn" not in result:
            result["issn"] = jissn


def _extract_schema_publisher(result: dict, item: dict) -> None:
    """Wyciągnij wydawcę."""
    publisher = item.get("publisher")
    if isinstance(publisher, dict):
        pub_name = publisher.get("name")
        if pub_name and "publisher" not in result:
            result["publisher"] = pub_name
    elif isinstance(publisher, str) and publisher and "publisher" not in result:
        result["publisher"] = publisher


def _extract_schema_volume_issue(result: dict, item: dict) -> None:
    """Wyciągnij tom i numer."""
    vol = item.get("volumeNumber")
    if vol and "volume" not in result:
        result["volume"] = str(vol)

    iss = item.get("issueNumber")
    if iss and "issue" not in result:
        result["issue"] = str(iss)


def _extract_schema_pages(result: dict, item: dict) -> None:
    """Wyciągnij strony."""
    pstart = item.get("pageStart")
    pend = item.get("pageEnd")
    if pstart and "pages" not in result:
        if pend:
            result["pages"] = f"{pstart}-{pend}"
        else:
            result["pages"] = str(pstart)
