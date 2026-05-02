"""Niskopoziomowe parsery: DOI, rok, nazwisko autora oraz pomocnicy meta-tagów."""

import re

from bs4 import BeautifulSoup

DOI_URL_PREFIXES = [
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
]


def _clean_doi(doi_str: str) -> str:
    """Wyczyść DOI z prefiksu URL."""
    if not doi_str:
        return ""
    doi_str = doi_str.strip()
    for prefix in DOI_URL_PREFIXES:
        if doi_str.lower().startswith(prefix.lower()):
            return doi_str[len(prefix) :]
    return doi_str


def _parse_year(date_str: str | None) -> int | None:
    """Wyciągnij 4-cyfrowy rok z tekstu daty."""
    if not date_str:
        return None
    match = re.search(r"\d{4}", date_str)
    if match:
        return int(match.group())
    return None


def _parse_author_name(name: str) -> dict:
    """Parsuj nazwisko autora na dict {family, given}."""
    name = name.strip()
    if not name:
        return {"family": "", "given": ""}

    if "," in name:
        parts = name.split(",", 1)
        return {
            "family": parts[0].strip(),
            "given": parts[1].strip(),
        }

    parts = name.rsplit(None, 1)
    if len(parts) == 2:
        return {
            "family": parts[1].strip(),
            "given": parts[0].strip(),
        }
    return {"family": parts[0].strip(), "given": ""}


def _get_meta(soup: BeautifulSoup, name: str) -> str | None:
    """Pobierz wartość content z meta tagu po name."""
    tag = soup.find("meta", attrs={"name": name})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None


def _get_all_meta(soup: BeautifulSoup, name: str) -> list[str]:
    """Pobierz wszystkie wartości content z meta tagów."""
    tags = soup.find_all("meta", attrs={"name": name})
    return [
        t["content"].strip() for t in tags if t.get("content") and t["content"].strip()
    ]


def _get_meta_property(soup: BeautifulSoup, prop: str) -> str | None:
    """Pobierz wartość content z meta tagu po property."""
    tag = soup.find("meta", attrs={"property": prop})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None
