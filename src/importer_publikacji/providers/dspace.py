"""DSpace provider with autodetection of DSpace 6/7.

URL format determines which API is used:
- /items/{uuid} → DSpace 7+ REST API
- /handle/{prefix}/{suffix} → DSpace 6 REST API

Ponadto provider rozpoznaje URL-e LIST (kolekcja/community/discover/
search — patrz ``split_input``) i enumeruje ich itemy przez REST, żeby
paczka wielo-prac (``MultipleWorksImport``, patrz ``providers/bibtex.py``
za wzorzec) zadziałała też dla DSpace.
"""

import logging
import re
from urllib.parse import ParseResult, parse_qs, urlparse

import requests

from . import (
    DataProvider,
    FetchedPublication,
    InputMode,
    SplitRecord,
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

logger = logging.getLogger(__name__)

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}"
    r"-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Bezpiecznik na paginacje enumeracji list (kolekcja/community/discover):
# kolekcje bywaja duze (setki-tysiace pozycji), a kazda strona to osobne
# zapytanie REST. Cap zapobiega niekontrolowanej liczbie requestow; przy
# obcieciu logujemy ostrzezenie (nie milczymy o utracie danych).
MAX_SPLIT_ITEMS = 500
_PAGE_SIZE = 100


def _fallback_to_www(identifier: str) -> FetchedPublication | None:
    """Spróbuj sparsować URL przez WWW provider (HTML scraping).

    Używane jako fallback gdy DSpace REST API nie zwróci poprawnych
    metadanych. Wyciągnięte do module-level funkcji żeby testy mogły
    ją łatwo mockować (patch importer_publikacji.providers.dspace.
    _fallback_to_www).
    """
    from .www.provider import WWWProvider

    return WWWProvider().fetch(identifier)


def _ensure_scheme_and_parse(url: str) -> ParseResult | None:
    """Doklej domyślny schemat i sparsuj URL; None jeśli oczywisty śmieć.

    Wspólny pierwszy krok dla wszystkich parserów URL w tym module —
    normalizuje "repo.example.com/..." do "https://repo.example.com/..."
    i odrzuca od razu wejście bez sensownego ``scheme``/``netloc``.
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

    return parsed


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
    parsed = _ensure_scheme_and_parse(url)
    if parsed is None:
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

    Uwaga: handle w DSpace 6 XMLUI jest DWUZNACZNY — ten sam kształt
    URL adresuje item, kolekcję i community (nie ma tego w ścieżce).
    Ten parser tylko wyciąga handle; rozstrzygnięcie typu (i routing
    item-vs-lista) należy do ``split_input``/``fetch`` wyżej, przez
    zapytanie REST ``/rest/handle/{handle}``.
    """
    parsed = _ensure_scheme_and_parse(url)
    if parsed is None:
        return None

    path = parsed.path.rstrip("/")

    match = re.search(r"/handle/(\d+/\d+)", path)
    if not match:
        return None

    handle = match.group(1)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    return base_url, handle


def _parse_dspace7_container_url(
    url: str,
) -> tuple[str, str, str] | None:
    """Parse DSpace 7+ container (list) URL.

    Formats:
    - https://repo.example.com/collections/{uuid}
    - https://repo.example.com/communities/{uuid}

    Returns (base_url, kind, uuid) where kind is "collections" or
    "communities", or None. Strukturalnie odrębny kształt od
    ``/items/{uuid}``/``/entities/...`` — DSpace 7+ Angular UI nie
    myli itemu z kontenerem (w przeciwieństwie do DSpace 6 handle).
    """
    parsed = _ensure_scheme_and_parse(url)
    if parsed is None:
        return None

    path = parsed.path.rstrip("/")

    match = re.match(
        r"^/(collections|communities)/"
        r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}"
        r"-[0-9a-f]{4}-[0-9a-f]{12})$",
        path,
        re.IGNORECASE,
    )
    if not match:
        return None

    base_url = f"{parsed.scheme}://{parsed.netloc}"
    return base_url, match.group(1), match.group(2)


def _parse_dspace7_discover_url(
    url: str,
) -> tuple[str, dict[str, str]] | None:
    """Parse DSpace 7+ discover/browse (search result) URL.

    Formats:
    - https://repo.example.com/search?query=...&scope=...
    - https://repo.example.com/browse/title?scope=...

    Zwraca (base_url, params) z opcjonalnymi kluczami "query"/"scope"
    przekazanymi dalej do REST ``/server/api/discover/search/objects``.
    Pozostałe parametry fasetowania (np. filtry ``f.*`` z ``/browse``)
    są świadomie pomijane — odtworzenie pełnej semantyki fasetowania
    UI nie jest celem tej funkcji, tylko enumeracja wynikowego zbioru
    itemów.
    """
    parsed = _ensure_scheme_and_parse(url)
    if parsed is None:
        return None

    path = parsed.path.rstrip("/") or "/"
    if path != "/search" and not path.startswith("/browse"):
        return None

    base_url = f"{parsed.scheme}://{parsed.netloc}"
    qs = parse_qs(parsed.query)
    params: dict[str, str] = {}
    if qs.get("query"):
        params["query"] = qs["query"][0]
    if qs.get("scope"):
        params["scope"] = qs["scope"][0]
    return base_url, params


def _canonical_discover7_url(base_url: str, params: dict[str, str]) -> str:
    """Kanoniczna postać znormalizowanego URL-a discover/search."""
    ordered = [(k, params[k]) for k in ("query", "scope") if params.get(k)]
    if not ordered:
        return f"{base_url}/search"
    qs = "&".join(f"{k}={v}" for k, v in ordered)
    return f"{base_url}/search?{qs}"


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
    api_url = f"{base_url}/server/api/core/items/{uuid}"

    try:
        resp = requests.get(api_url, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException:
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
    api_url = f"{base_url}/rest/handle/{handle}?expand=metadata"

    try:
        resp = requests.get(api_url, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException:
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


def _dspace6_resolve_handle_type(base_url: str, handle: str) -> dict | None:
    """GET /rest/handle/{handle} (bez expand) — tylko żeby poznać "type".

    Zwraca dict z co najmniej "type" ("item"/"collection"/"community")
    i "uuid", albo None przy błędzie sieci/HTTP. Rozstrzyga latentny bug:
    handle w DSpace 6 nie odróżnia w URL-u itemu od kontenera.
    """
    url = f"{base_url}/rest/handle/{handle}"
    try:
        resp = requests.get(url, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException:
        logger.warning(
            "DSpace6: nie udalo sie rozpoznac typu handle %s na %s",
            handle,
            base_url,
        )
        return None
    return resp.json()


def _dspace6_paginate_items(
    base_url: str,
    collection_uuid: str,
    max_items: int = MAX_SPLIT_ITEMS,
    page_size: int = _PAGE_SIZE,
) -> list[dict]:
    """Enumeruj itemy kolekcji DSpace 6 przez REST, z paginacją.

    ``GET /rest/collections/{uuid}/items?limit=&offset=``. Zatrzymuje
    się, gdy strona jest krótsza niż żądany limit (koniec danych), przy
    błędzie REST (log + zwrot dotychczasowego wyniku), albo po
    osiągnięciu ``max_items`` (log ostrzeżenia o obcięciu).
    """
    items: list[dict] = []
    offset = 0
    while len(items) < max_items:
        limit = min(page_size, max_items - len(items))
        try:
            resp = requests.get(
                f"{base_url}/rest/collections/{collection_uuid}/items",
                params={"limit": limit, "offset": offset},
                timeout=FETCH_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException:
            logger.warning(
                "DSpace6: blad pobierania items kolekcji %s (offset=%d)",
                collection_uuid,
                offset,
            )
            break
        page = resp.json() or []
        if not page:
            break
        items.extend(page)
        if len(page) < limit:
            break
        offset += len(page)

    if len(items) >= max_items:
        logger.warning(
            "DSpace6: kolekcja %s ma wiecej niz %d pozycji — wynik obcieto.",
            collection_uuid,
            max_items,
        )
    return items[:max_items]


def _dspace6_community_collection_uuids(
    base_url: str, community_uuid: str
) -> list[str]:
    """GET /rest/communities/{uuid}/collections — uuidy kolekcji-dzieci."""
    try:
        resp = requests.get(
            f"{base_url}/rest/communities/{community_uuid}/collections",
            timeout=FETCH_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException:
        logger.warning(
            "DSpace6: blad pobierania kolekcji community %s",
            community_uuid,
        )
        return []
    return [c["uuid"] for c in (resp.json() or []) if c.get("uuid")]


def _items_to_dspace6_records(base_url: str, items: list[dict]) -> list[SplitRecord]:
    records = []
    for item in items:
        handle = item.get("handle")
        if not handle:
            continue
        records.append(
            SplitRecord(raw=f"{base_url}/handle/{handle}", title=item.get("name", ""))
        )
    return records


def _split_dspace6_collection(
    base_url: str, collection_uuid: str, fallback_url: str
) -> list[SplitRecord]:
    items = _dspace6_paginate_items(base_url, collection_uuid)
    records = _items_to_dspace6_records(base_url, items)
    return records or [SplitRecord(raw=fallback_url)]


def _split_dspace6_community(
    base_url: str, community_uuid: str, fallback_url: str
) -> list[SplitRecord]:
    collection_uuids = _dspace6_community_collection_uuids(base_url, community_uuid)
    all_items: list[dict] = []
    for coll_uuid in collection_uuids:
        if len(all_items) >= MAX_SPLIT_ITEMS:
            break
        remaining = MAX_SPLIT_ITEMS - len(all_items)
        all_items.extend(
            _dspace6_paginate_items(base_url, coll_uuid, max_items=remaining)
        )
    records = _items_to_dspace6_records(base_url, all_items)
    return records or [SplitRecord(raw=fallback_url)]


def _dspace7_discover_page(
    base_url: str,
    scope: str | None,
    query: str | None,
    page: int,
    size: int,
) -> dict | None:
    """Pobierz jedną stronę ``discover/search/objects``, albo None przy
    błędzie REST (log ostrzeżenia)."""
    params = {"dsoType": "item", "page": page, "size": size}
    if scope:
        params["scope"] = scope
    if query:
        params["query"] = query
    try:
        resp = requests.get(
            f"{base_url}/server/api/discover/search/objects",
            params=params,
            timeout=FETCH_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException:
        logger.warning(
            "DSpace7: blad discover search (scope=%s, query=%s, page=%d)",
            scope,
            query,
            page,
        )
        return None
    data = resp.json()
    return data.get("_embedded", {}).get("searchResult", {})


def _dspace7_discover_items(
    base_url: str,
    scope: str | None = None,
    query: str | None = None,
    max_items: int = MAX_SPLIT_ITEMS,
    page_size: int = 20,
) -> list[dict]:
    """Enumeruj wyniki discover DSpace 7+ przez REST, z paginacją.

    ``GET /server/api/discover/search/objects?dsoType=item&page=&size=``,
    opcjonalnie ``scope=``/``query=``. Zatrzymuje się na ``page >=
    totalPages`` (z odpowiedzi HAL) albo krótszej niż żądana stronie,
    przy błędzie REST (log + zwrot dotychczasowego wyniku), albo po
    osiągnięciu ``max_items`` (log ostrzeżenia o obcięciu).
    """
    items: list[dict] = []
    page = 0
    while len(items) < max_items:
        size = min(page_size, max_items - len(items))
        search_result = _dspace7_discover_page(base_url, scope, query, page, size)
        if search_result is None:
            break
        objects = search_result.get("_embedded", {}).get("objects", [])
        if not objects:
            break
        items.extend(
            dso
            for obj in objects
            if (dso := obj.get("_embedded", {}).get("indexableObject"))
        )
        total_pages = search_result.get("page", {}).get("totalPages")
        page += 1
        if total_pages is not None and page >= total_pages:
            break
        if len(objects) < size:
            break

    if len(items) >= max_items:
        logger.warning(
            "DSpace7: discover (scope=%s, query=%s) ma wiecej niz %d "
            "pozycji — wynik obcieto.",
            scope,
            query,
            max_items,
        )
    return items[:max_items]


def _items_to_dspace7_records(base_url: str, items: list[dict]) -> list[SplitRecord]:
    records = []
    for item in items:
        uuid = item.get("uuid")
        if not uuid:
            continue
        records.append(
            SplitRecord(raw=f"{base_url}/items/{uuid}", title=item.get("name", ""))
        )
    return records


def _split_dspace7_list(
    base_url: str,
    fallback_url: str,
    scope: str | None = None,
    query: str | None = None,
) -> list[SplitRecord]:
    items = _dspace7_discover_items(base_url, scope=scope, query=query)
    records = _items_to_dspace7_records(base_url, items)
    return records or [SplitRecord(raw=fallback_url)]


def _split_dspace_input(url: str) -> list[SplitRecord]:
    """Rdzeń ``DSpaceProvider.split_input`` — wyodrębniona funkcja modułu,
    żeby ``fetch()`` mogła jej użyć jako siatki bezpieczeństwa (patrz
    ``_resolve_single_item_from_list``) bez rekurencyjnego tworzenia
    instancji providera.
    """
    url = url.strip()
    if not url:
        return [SplitRecord(raw=url)]

    container7 = _parse_dspace7_container_url(url)
    if container7 is not None:
        base_url, _kind, uuid = container7
        return _split_dspace7_list(base_url, url, scope=uuid)

    discover7 = _parse_dspace7_discover_url(url)
    if discover7 is not None:
        base_url, params = discover7
        return _split_dspace7_list(
            base_url, url, scope=params.get("scope"), query=params.get("query")
        )

    handle_result = _parse_handle_url(url)
    if handle_result is not None:
        base_url, handle = handle_result
        resolved = _dspace6_resolve_handle_type(base_url, handle)
        if resolved is not None:
            kind = resolved.get("type")
            uuid = resolved.get("uuid")
            if kind == "collection" and uuid:
                return _split_dspace6_collection(base_url, uuid, url)
            if kind == "community" and uuid:
                return _split_dspace6_community(base_url, uuid, url)
        # kind == "item" (albo siec padla, resolved is None) -> traktuj
        # jak pojedynczy item; fetch() go rozwiaze normalnie nizej.

    return [SplitRecord(raw=url)]


def _resolve_single_item_from_list(url: str) -> str | None:
    """Siatka bezpieczeństwa dla ``FetchView.post`` (``views/wizard.py``).

    Gdy ``split_input()`` zwróci dokładnie 1 ``SplitRecord`` (np. lista
    z dokładnie jednym itemem), wywołanie idzie ścieżką pojedynczej sesji
    z ``identifier=<oryginalny URL listy>`` — NIE z URL-em itemu (patrz
    ``_create_batch``/próg ``len(records) >= 2`` w ``FetchView.post``).
    Bez tej funkcji ``fetch()`` próbowałby (błędnie) potraktować URL listy
    jak URL itemu. Zwraca URL rozwiązanego itemu, albo None gdy ``url``
    strukturalnie nie jest listą (żeby nie robić zbędnych zapytań REST).
    """
    records = _split_dspace_input(url)
    if len(records) != 1:
        return None
    candidate = records[0].raw
    if candidate == url:
        return None
    return candidate


@register_provider
class DSpaceProvider(DataProvider):
    @property
    def name(self) -> str:
        return "DSpace"

    @property
    def identifier_label(self) -> str:
        return "Adres strony WWW w repozytorium DSpace"

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
        if result is not None:
            base_url, ident, version = result
            if version == "7":
                return f"{base_url}/items/{ident}"
            return f"{base_url}/handle/{ident}"

        # URL-e listowe (kolekcja/community/discover/search) DSpace 7+ —
        # mają odrębny kształt ścieżki od /items/ i /entities/, więc
        # dotąd twardo odrzucane. Handle-based URL-e DSpace 6 (item vs.
        # kolekcja vs. community) już dziś przechodzą powyższy branch
        # (regex nie odróżnia typu) — routing pojedynczy-item-vs-lista
        # dzieje się w ``split_input``, nie tutaj.
        container7 = _parse_dspace7_container_url(identifier)
        if container7 is not None:
            base_url, kind, uuid = container7
            return f"{base_url}/{kind}/{uuid}"

        discover7 = _parse_dspace7_discover_url(identifier)
        if discover7 is not None:
            base_url, params = discover7
            return _canonical_discover7_url(base_url, params)

        return None

    def split_input(self, text: str) -> list[SplitRecord]:
        """Rozbij URL listy DSpace (kolekcja/community/discover/search)
        na jeden ``SplitRecord`` per item; URL pojedynczego itemu (albo
        cokolwiek nierozpoznane) → 1 rekord, dzisiejsze zachowanie."""
        return _split_dspace_input(text)

    def fetch(self, identifier: str) -> FetchedPublication | None:
        fetch_identifier = identifier
        parsed = _parse_dspace_url(identifier)
        if parsed is None:
            # Moze to byc URL listy (kolekcja/community/discover), ktora
            # split_input() rozwiazuje do dokladnie JEDNEGO itemu — wtedy
            # FetchView.post idzie sciezka pojedynczej sesji z
            # identifier=<oryginalny URL listy> (patrz
            # _resolve_single_item_from_list). W przeciwnym razie (0 lub
            # ident nierozpoznany) fetch po prostu nie ma czego pobrac.
            single_item_url = _resolve_single_item_from_list(identifier)
            if single_item_url is None:
                return None
            parsed = _parse_dspace_url(single_item_url)
            if parsed is None:
                return None
            # WWW fallback nizej ma probowac itemu, nie oryginalnego
            # URL-a listy (ktorego HTML nie zawiera metadanych publikacji).
            fetch_identifier = single_item_url

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
        return _fallback_to_www(fetch_identifier)
