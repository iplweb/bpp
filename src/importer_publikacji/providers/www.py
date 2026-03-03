"""Importuj pracę po danych ze strony WWW."""

import json
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from . import (
    DataProvider,
    FetchedPublication,
    InputMode,
    register_provider,
)

FETCH_TIMEOUT = 15

# Omega-PSIR article identifier pattern
OMEGA_ARTICLE_RE = re.compile(r"/info/article/([A-Za-z]{2,5}[0-9a-f]{32})")

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


# --- Extractors ---


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
    """Pobierz JSON-LD z Omega-PSIR REST API."""
    api_url = f"{base_url}/seam/resource/rest/accesspoint/rdf/jsonld/{identifier}"
    try:
        resp = requests.get(api_url, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException:
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


ABSTRACT_LABELS = {
    "abstract": "en",
    "streszczenie": "pl",
    "streszczenie w języku polskim": "pl",
    "streszczenie w języku angielskim": "en",
    "summary": "en",
}

MIN_ABSTRACT_LENGTH = 20


def _extract_body_abstracts(
    soup: BeautifulSoup,
) -> list[dict]:
    """Wyciągnij streszczenia z body HTML.

    Szuka nagłówków (h1-h6, dt, strong, b, label, th)
    pasujących do ABSTRACT_LABELS i pobiera tekst
    z następnego elementu rodzeństwa.
    """
    heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}
    label_tags = {"strong", "b", "label"}
    all_tags = heading_tags | label_tags | {"dt", "th"}

    results = []
    seen_texts = set()

    for tag in soup.find_all(all_tags):
        text = tag.get_text(strip=True).lower()
        # Usuń dwukropek i białe znaki z końca
        text = text.rstrip(": \t")
        if text not in ABSTRACT_LABELS:
            continue

        language = ABSTRACT_LABELS[text]
        content = _get_abstract_content(tag)

        if not content or len(content) < MIN_ABSTRACT_LENGTH:
            continue

        # Deduplikacja po treści
        if content in seen_texts:
            continue
        seen_texts.add(content)

        results.append({"text": content, "language": language})

    return results


def _get_abstract_content(tag) -> str | None:
    """Pobierz tekst streszczenia z elementu."""
    tag_name = tag.name

    if tag_name == "dt":
        dd = tag.find_next_sibling("dd")
        if dd:
            return dd.get_text(strip=True)
        return None

    if tag_name == "th":
        return _get_th_content(tag)

    # h1-h6, strong, b, label
    sibling = tag.find_next_sibling()
    if sibling:
        return sibling.get_text(strip=True)

    # strong/b wewnatrz akapitu -- tekst po tagu
    if tag_name in {"strong", "b"}:
        return _get_inline_tag_trailing_text(tag)

    return None


def _get_th_content(tag) -> str | None:
    """Pobierz tekst z td obok th."""
    td = tag.find_next_sibling("td")
    if not td:
        # Sprobuj w tym samym wierszu
        tr = tag.parent
        if tr and tr.name == "tr":
            td = tr.find("td")
    if td:
        return td.get_text(strip=True)
    return None


def _get_inline_tag_trailing_text(tag) -> str | None:
    """Pobierz tekst po tagu strong/b w rodzicu."""
    parent = tag.parent
    if not parent:
        return None
    remaining = ""
    found_tag = False
    for child in parent.children:
        if child is tag:
            found_tag = True
            continue
        if found_tag:
            if hasattr(child, "get_text"):
                remaining += child.get_text(strip=True)
            else:
                remaining += str(child).strip()
    if remaining.strip():
        return remaining.strip()
    return None


def _extract_opengraph(soup: BeautifulSoup) -> dict:
    """Wyciągnij dane z OpenGraph meta tagów (fallback)."""
    result = {}
    title = _get_meta_property(soup, "og:title")
    if title:
        result["title"] = title
    return result


def _merge_sources(sources: list[dict]) -> dict:
    """Scal wyniki z wielu extractorów.

    Pierwszy niepusty wynik dla każdego pola wygrywa.
    Dla list (authors, keywords) — pierwsza niepusta lista.
    """
    merged = {}
    list_fields = {"authors", "keywords"}

    for source in sources:
        for key, value in source.items():
            if key in merged:
                continue
            if key in list_fields:
                if isinstance(value, list) and value:
                    merged[key] = value
            elif value is not None and value != "":
                merged[key] = value

    return merged


def _fetch_page(
    url: str,
) -> tuple[str, BeautifulSoup] | None:
    """Pobierz stronę i zwróć (html, soup)."""
    try:
        resp = requests.get(
            url,
            timeout=FETCH_TIMEOUT,
            headers={
                "User-Agent": ("Mozilla/5.0 (compatible; BPP-Importer/1.0)"),
            },
        )
        resp.raise_for_status()
    except requests.RequestException:
        return None
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    return html, soup


def _validate_url(url: str) -> str | None:
    """Waliduj i znormalizuj URL."""
    url = url.strip()
    if not url:
        return None

    if "://" not in url:
        url = "https://" + url

    try:
        parsed = urlparse(url)
    except ValueError:
        return None

    if not parsed.scheme or not parsed.netloc:
        return None

    if parsed.scheme not in ("http", "https"):
        return None

    return url


@register_provider
class WWWProvider(DataProvider):
    @property
    def name(self) -> str:
        return "Pozostałe strony WWW"

    @property
    def identifier_label(self) -> str:
        return "Adres URL strony z publikacją"

    @property
    def input_mode(self) -> str:
        return InputMode.IDENTIFIER

    @property
    def input_placeholder(self) -> str:
        return "https://example.edu.pl/article/..."

    @property
    def input_help_text(self) -> str:
        return (
            "Wklej adres strony z danymi publikacji. "
            "Obsługiwane źródła danych: "
            "citation_* meta tagi, Dublin Core, "
            "Schema.org JSON-LD, Omega-PSIR, "
            "OpenGraph."
        )

    def validate_identifier(self, identifier: str) -> str | None:
        return _validate_url(identifier)

    def fetch(self, identifier: str) -> FetchedPublication | None:
        url = _validate_url(identifier)
        if not url:
            return None

        page = _fetch_page(url)
        if page is None:
            return None
        _html, soup = page

        sources = []
        sources_used = []

        _collect_citation_sources(url, soup, sources, sources_used)
        _collect_schema_sources(soup, sources, sources_used)
        _collect_fallback_sources(soup, sources, sources_used)

        merged = _merge_sources(sources)
        title = merged.pop("title", None)
        if not title:
            return None

        # Ekstrakcja streszczeń z body HTML
        body_abstracts = _extract_body_abstracts(soup)
        extra = {"original_url": url}
        if body_abstracts:
            extra["abstracts"] = body_abstracts

        # Jeśli brak abstractu z meta tagów,
        # użyj pierwszego z body
        abstract = merged.get("abstract")
        if not abstract and body_abstracts:
            abstract = body_abstracts[0]["text"]

        return FetchedPublication(
            raw_data={
                "url": url,
                "sources_used": sources_used,
            },
            title=title,
            doi=merged.get("doi"),
            year=merged.get("year"),
            authors=merged.get("authors", []),
            source_title=merged.get("source_title"),
            source_abbreviation=merged.get("source_abbreviation"),
            issn=merged.get("issn"),
            isbn=merged.get("isbn"),
            publisher=merged.get("publisher"),
            language=merged.get("language"),
            abstract=abstract,
            volume=merged.get("volume"),
            issue=merged.get("issue"),
            pages=merged.get("pages"),
            url=url,
            keywords=merged.get("keywords", []),
            extra=extra,
        )


def _collect_citation_sources(
    url: str,
    soup: BeautifulSoup,
    sources: list,
    sources_used: list,
) -> None:
    """Zbierz citation_* i Omega-PSIR źródła."""
    # 1. citation_* meta tagi (najwyższy priorytet)
    citation = _extract_citation_meta(soup)
    if citation:
        sources.append(citation)
        sources_used.append("citation_meta")

    # 2. Omega-PSIR JSON-LD (jeśli URL pasuje)
    omega = _detect_omega_psir(url)
    if omega:
        jsonld = _fetch_omega_psir_jsonld(*omega)
        if jsonld:
            parsed = _parse_omega_jsonld(jsonld)
            if parsed:
                sources.append(parsed)
                sources_used.append("omega_psir")


def _collect_schema_sources(
    soup: BeautifulSoup,
    sources: list,
    sources_used: list,
) -> None:
    """Zbierz Schema.org i Dublin Core źródła."""
    # 3. Schema.org JSON-LD z HTML
    schema = _extract_schema_jsonld(soup)
    if schema:
        sources.append(schema)
        sources_used.append("schema_jsonld")

    # 4. Dublin Core
    dc = _extract_dublin_core(soup)
    if dc:
        sources.append(dc)
        sources_used.append("dublin_core")


def _collect_fallback_sources(
    soup: BeautifulSoup,
    sources: list,
    sources_used: list,
) -> None:
    """Zbierz fallback (OpenGraph) źródła."""
    # 5. OpenGraph (fallback)
    og = _extract_opengraph(soup)
    if og:
        sources.append(og)
        sources_used.append("opengraph")
