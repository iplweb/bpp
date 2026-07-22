"""Detekcja, pobranie i parsing danych z systemu Omega-PSIR (REST JSON-LD)."""

import re
from urllib.parse import urlparse

from .network import safe_get
from .parsers import _clean_doi, _parse_year

FETCH_TIMEOUT = 15

# Omega-PSIR article identifier pattern
OMEGA_ARTICLE_RE = re.compile(r"/info/article/([A-Za-z]{2,5}[0-9a-f]{32})")


def _detect_omega_psir(
    url: str,
) -> tuple[str, str] | None:
    """Wykryj URL Omega-PSIR, zwróć (base_url, id)."""
    match = OMEGA_ARTICLE_RE.search(url)
    if not match:
        return None
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    return base_url, match.group(1)


def _fetch_omega_psir_jsonld(base_url: str, identifier: str) -> list | None:
    """Pobierz JSON-LD z Omega-PSIR REST API.

    SSRF-guard: base_url pochodzi z URL-a użytkownika, a REST API może
    przekierować — safe_get waliduje host przy każdym hopie (bez tego publiczny
    host mógłby przekierować importer na adres wewnętrzny).
    """
    api_url = f"{base_url}/seam/resource/rest/accesspoint/rdf/jsonld/{identifier}"
    resp = safe_get(api_url, timeout=FETCH_TIMEOUT)
    if resp is None:
        return None
    try:
        return resp.json()
    except (ValueError, TypeError):
        return None


def _parse_omega_jsonld(data: list) -> dict:
    """Parsuj JSON-LD z Omega-PSIR na dict."""
    if not data or not isinstance(data, list):
        return {}

    index = {
        item["@id"]: item for item in data if isinstance(item, dict) and "@id" in item
    }

    article = _find_omega_article(data)
    if not article:
        return {}

    result = {}
    _extract_omega_title(result, article)
    _extract_omega_authors(result, article, index)
    _extract_omega_journal_info(result, article, index)
    _extract_omega_date(result, article)
    _extract_omega_doi(result, article)
    _extract_omega_language(result, article)

    return result


def _find_omega_article(data: list) -> dict | None:
    """Znajdź artykuł w JSON-LD."""
    for item in data:
        if not isinstance(item, dict):
            continue
        item_type = item.get("@type", "")
        if isinstance(item_type, list):
            type_str = " ".join(item_type)
        else:
            type_str = str(item_type)
        if "Article" in type_str:
            return item
    return None


def _extract_omega_title(result: dict, article: dict) -> None:
    """Wyciągnij tytuł z artykułu."""
    title = article.get("name")
    if title:
        result["title"] = title


def _extract_omega_authors(result: dict, article: dict, index: dict) -> None:
    """Wyciągnij autorów z artykułu."""
    author_refs = article.get("author", [])
    if not isinstance(author_refs, list):
        author_refs = [author_refs]
    authors = []
    for ref in author_refs:
        if isinstance(ref, dict) and "@id" in ref:
            person = index.get(ref["@id"], ref)
        elif isinstance(ref, dict):
            person = ref
        else:
            continue
        family = person.get("familyName", "")
        given = person.get("givenName", "")
        if family or given:
            authors.append({"family": family, "given": given})
    if authors:
        result["authors"] = authors


def _extract_omega_journal_info(result: dict, article: dict, index: dict) -> None:
    """Wyciągnij informacje o czasopiśmie."""
    part_of = article.get("isPartOf")
    if isinstance(part_of, dict) and "@id" in part_of:
        issue_obj = index.get(part_of["@id"], part_of)
    elif isinstance(part_of, dict):
        issue_obj = part_of
    else:
        issue_obj = None

    if not issue_obj:
        return

    issue_num = issue_obj.get("issueNumber") or issue_obj.get("number")
    if issue_num:
        result["issue"] = str(issue_num)

    vol = issue_obj.get("volumeNumber")
    if vol:
        result["volume"] = str(vol)

    _extract_omega_journal_details(result, issue_obj, index)


def _extract_omega_journal_details(result: dict, issue_obj: dict, index: dict) -> None:
    """Wyciągnij szczegóły czasopisma."""
    journal_ref = issue_obj.get("isPartOf")
    if isinstance(journal_ref, dict):
        jid = journal_ref.get("@id")
        journal = index.get(jid, journal_ref) if jid else journal_ref
    else:
        journal = None

    if not journal:
        return

    jname = journal.get("name")
    if jname:
        result["source_title"] = jname
    jissn = journal.get("issn")
    if jissn:
        result["issn"] = jissn
    jpub = journal.get("publisher")
    if isinstance(jpub, dict):
        pub_name = jpub.get("name")
        if pub_name:
            result["publisher"] = pub_name
    elif isinstance(jpub, str) and jpub:
        result["publisher"] = jpub


def _extract_omega_date(result: dict, article: dict) -> None:
    """Wyciągnij datę publikacji."""
    date_pub = article.get("datePublished")
    if date_pub:
        year = _parse_year(str(date_pub))
        if year:
            result["year"] = year


def _extract_omega_doi(result: dict, article: dict) -> None:
    """Wyciągnij DOI."""
    doi = article.get("prism:doi") or article.get("doi")
    if doi:
        result["doi"] = _clean_doi(str(doi))


def _extract_omega_language(result: dict, article: dict) -> None:
    """Wyciągnij język."""
    lang = article.get("inLanguage")
    if lang:
        result["language"] = str(lang)
