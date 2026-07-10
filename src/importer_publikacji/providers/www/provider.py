"""Klasa ``WWWProvider`` — wpięcie ekstraktorów w pipeline DataProvider."""

from bs4 import BeautifulSoup

from .. import (
    DataProvider,
    FetchedPublication,
    InputMode,
    register_provider,
)
from .body_abstracts import _extract_body_abstracts
from .citation_meta import _extract_citation_meta
from .dublin_core import _extract_dublin_core
from .merge import _merge_sources
from .network import _fetch_page, _validate_url
from .omega_psir import (
    _detect_omega_psir,
    _fetch_omega_psir_jsonld,
    _parse_omega_jsonld,
)
from .opengraph import _extract_opengraph
from .schema_jsonld import _extract_schema_jsonld


@register_provider
class WWWProvider(DataProvider):
    @property
    def name(self) -> str:
        return "Pozostałe strony WWW"

    @property
    def identifier_label(self) -> str:
        return "Adres URL strony z publikacją"

    @property
    def icon(self) -> str:
        return "fi-link-external"

    @property
    def landing_caption(self) -> str:
        return (
            "Wyciągnij dane ze strony publikacji (meta tagi, Dublin "
            "Core, Schema.org, Omega-PSIR)."
        )

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
