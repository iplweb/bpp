"""DSpace provider with autodetection of DSpace 6/7.

URL format determines which API is used:
- /items/{uuid} → DSpace 7+ REST API
- /handle/{prefix}/{suffix} → DSpace 6 REST API
"""

import re
from urllib.parse import urlparse

from . import (
    DataProvider,
    FetchedPublication,
    InputMode,
    register_provider,
)
from .dspace_common import (
    DSPACE_TYPE_MAP,
    FETCH_TIMEOUT,
    _build_extra_data,
    _extract_doi,
    _extract_volume_issue_pages,
    _get_dc_value,
    _get_dc_values,
    _normalize_metadata,
    _parse_citation_string,
    _parse_dspace_authors,
    _parse_year,
    _resolve_url,
)

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}"
    r"-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _fallback_to_www(identifier: str) -> FetchedPublication | None:
    """Spróbuj sparsować URL przez WWW provider (HTML scraping).

    Używane jako fallback gdy DSpace REST API nie zwróci poprawnych
    metadanych. Wyciągnięte do module-level funkcji żeby testy mogły
    ją łatwo mockować (patch importer_publikacji.providers.dspace.
    _fallback_to_www).
    """
    from .www.provider import WWWProvider

    return WWWProvider().fetch(identifier)


def _parse_dspace7_url(
    url: str,
) -> tuple[str, str] | None:
    """Parse DSpace 7 URL, return (base_url, uuid).

    Formats:
    - https://repo.example.com/items/{uuid}
    - https://repo.example.com/items/{uuid}/full
    - https://repo.example.com/entities/{type}/{uuid}
    - https://repo.example.com/entities/{type}/{uuid}/details

    DSpace 7+ Angular UI routuje "entities" (typed view) i "items"
    (generic view) na ten sam obiekt — REST API endpoint dla obu to
    /server/api/core/items/{uuid}.
    """
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

    path = parsed.path.rstrip("/")

    match = re.search(
        r"/(?:items|entities/[^/]+)/"
        r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}"
        r"-[0-9a-f]{4}-[0-9a-f]{12})",
        path,
        re.IGNORECASE,
    )
    if not match:
        return None

    uuid = match.group(1)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    return base_url, uuid


def _parse_handle_url(
    url: str,
) -> tuple[str, str] | None:
    """Parse DSpace 6 handle URL, return (base_url, handle).

    Formats:
    - https://repo.example.com/handle/123456789/922
    - https://repo.example.com/xmlui/handle/123/456
    """
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

    path = parsed.path.rstrip("/")

    match = re.search(r"/handle/(\d+/\d+)", path)
    if not match:
        return None

    handle = match.group(1)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    return base_url, handle


def _parse_dspace_url(
    url: str,
) -> tuple[str, str, str] | None:
    """Parse DSpace URL (either version).

    Returns (base_url, identifier, version) where version
    is "7" or "6", or None if not a valid DSpace URL.
    """
    result7 = _parse_dspace7_url(url)
    if result7:
        return result7[0], result7[1], "7"

    result6 = _parse_handle_url(url)
    if result6:
        return result6[0], result6[1], "6"

    return None


def _fetch_dspace7(base_url: str, uuid: str) -> FetchedPublication | None:
    """Fetch publication from DSpace 7+ REST API."""
    # SSRF-guard: base_url pochodzi wprost z URL-a użytkownika. safe_get
    # odrzuca hosty loopback/prywatne/link-local (metadata cloud) i śledzi
    # redirecty z rewalidacją każdego hopu (wspólny guard z providerem WWW).
    from .www.network import safe_get

    api_url = f"{base_url}/server/api/core/items/{uuid}"

    resp = safe_get(api_url, timeout=FETCH_TIMEOUT)
    if resp is None:
        return None

    data = resp.json()
    metadata = _normalize_metadata(data.get("metadata", []))

    title = _get_dc_value(metadata, "dc.title")
    if not title:
        return None

    authors = _parse_dspace_authors(metadata)
    year = _parse_year(_get_dc_value(metadata, "dc.date.issued"))
    volume, issue, pages = _extract_volume_issue_pages(metadata)

    dc_type = _get_dc_value(metadata, "dc.type")
    publication_type = DSPACE_TYPE_MAP.get(dc_type.lower()) if dc_type else None

    doi = _extract_doi(metadata)
    extra = _build_extra_data(metadata)

    return FetchedPublication(
        raw_data=data,
        title=title,
        doi=doi,
        year=year,
        authors=authors,
        source_title=_get_dc_value(metadata, "dc.relation.ispartof"),
        issn=_get_dc_value(metadata, "dc.identifier.issn"),
        isbn=_get_dc_value(metadata, "dc.identifier.isbn"),
        publisher=_get_dc_value(metadata, "dc.publisher"),
        publication_type=publication_type,
        language=_get_dc_value(metadata, "dc.language.iso"),
        abstract=_get_dc_value(metadata, "dc.description.abstract"),
        volume=volume,
        issue=issue,
        pages=pages,
        url=_resolve_url(metadata),
        license_url=_get_dc_value(metadata, "dc.rights.uri"),
        keywords=_get_dc_values(metadata, "dc.subject"),
        extra=extra,
    )


def _fetch_dspace6(base_url: str, handle: str) -> FetchedPublication | None:
    """Fetch publication from DSpace 6 REST API."""
    # SSRF-guard — patrz _fetch_dspace7.
    from .www.network import safe_get

    api_url = f"{base_url}/rest/handle/{handle}?expand=metadata"

    resp = safe_get(api_url, timeout=FETCH_TIMEOUT)
    if resp is None:
        return None

    data = resp.json()
    metadata = data.get("metadata", [])

    title = _get_dc_value(metadata, "dc.title")
    if not title:
        return None

    authors = _parse_dspace_authors(metadata)
    year = _parse_year(_get_dc_value(metadata, "dc.date.issued"))

    # DSpace 6: try explicit fields first,
    # then dcterms.bibliographicCitation
    volume, issue, pages = _extract_volume_issue_pages(metadata)
    if not volume and not issue and not pages:
        citation = _get_dc_value(metadata, "dcterms.bibliographicCitation")
        if citation:
            volume, issue, pages = _parse_citation_string(citation)

    dc_type = _get_dc_value(metadata, "dc.type")
    publication_type = DSPACE_TYPE_MAP.get(dc_type.lower()) if dc_type else None

    doi = _extract_doi(metadata)

    # DSpace 6: citation key is dcterms
    extra = _build_extra_data(
        metadata,
        citation_key="dcterms.bibliographicCitation",
    )

    # DSpace 6: source_title may be in dcterms.title
    # or dc.relation.ispartof
    source_title = _get_dc_value(metadata, "dc.relation.ispartof") or _get_dc_value(
        metadata, "dcterms.title"
    )

    # URL: handle → hdl.handle.net, fallback
    # na dc.identifier.uri (tylko jeśli to URL)
    raw_handle = data.get("handle")
    if raw_handle:
        url = f"https://hdl.handle.net/{raw_handle}"
    else:
        uri = _get_dc_value(metadata, "dc.identifier.uri")
        url = uri if uri and uri.startswith("http") else None

    return FetchedPublication(
        raw_data=data,
        title=title,
        doi=doi,
        year=year,
        authors=authors,
        source_title=source_title,
        issn=_get_dc_value(metadata, "dc.identifier.issn"),
        isbn=_get_dc_value(metadata, "dc.identifier.isbn"),
        publisher=_get_dc_value(metadata, "dc.publisher"),
        publication_type=publication_type,
        language=_get_dc_value(metadata, "dc.language.iso"),
        abstract=_get_dc_value(metadata, "dc.description.abstract"),
        volume=volume,
        issue=issue,
        pages=pages,
        url=url,
        license_url=_get_dc_value(metadata, "dc.rights.uri"),
        keywords=_get_dc_values(metadata, "dc.subject"),
        extra=extra,
    )


@register_provider
class DSpaceProvider(DataProvider):
    @property
    def name(self) -> str:
        return "DSpace"

    @property
    def identifier_label(self) -> str:
        return "Adres strony WWW w repozytorium DSpace"

    @property
    def icon(self) -> str:
        return "fi-database"

    @property
    def landing_caption(self) -> str:
        return "Pobierz dane z repozytorium DSpace po adresie strony."

    @property
    def input_mode(self) -> str:
        return InputMode.IDENTIFIER

    @property
    def input_placeholder(self) -> str:
        return (
            "https://repozytorium.example.edu.pl"
            "/items/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            " lub /handle/123456789/123"
        )

    @property
    def input_help_text(self) -> str:
        return (
            "Wklej URL publikacji z repozytorium DSpace. "
            "Obsługiwane formaty: "
            "/items/{uuid} (DSpace 7+) oraz "
            "/handle/{prefix}/{suffix} (DSpace 6)"
        )

    def validate_identifier(self, identifier: str) -> str | None:
        result = _parse_dspace_url(identifier)
        if result is None:
            return None
        base_url, ident, version = result
        if version == "7":
            return f"{base_url}/items/{ident}"
        return f"{base_url}/handle/{ident}"

    def fetch(self, identifier: str) -> FetchedPublication | None:
        parsed = _parse_dspace_url(identifier)
        if parsed is None:
            return None

        base_url, ident, version = parsed
        if version == "7":
            result = _fetch_dspace7(base_url, ident)
        else:
            result = _fetch_dspace6(base_url, ident)

        if result is not None:
            return result

        # Fallback: DSpace REST API zawiodło (404, 5xx, brak dc.title,
        # SPA bez metadanych w API). Spróbuj sparsować stronę HTML
        # przez WWW provider — często strona zawiera DOI/citation_*
        # metatagi nawet gdy REST API nie odpowiada.
        return _fallback_to_www(identifier)
