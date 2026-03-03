"""Shared helpers for DSpace 6 and DSpace 7 providers."""

import re

# Mapowanie typów DSpace (dc.type) → CrossRef-compatible
DSPACE_TYPE_MAP = {
    "article": "journal-article",
    "journal article": "journal-article",
    "book": "book",
    "book chapter": "book-chapter",
    "conference paper": "proceedings-article",
    "conference object": "proceedings-article",
    "conference contribution": "proceedings-article",
    "thesis": "dissertation",
    "doctoral thesis": "dissertation",
    "master thesis": "dissertation",
    "bachelor thesis": "dissertation",
    "report": "report",
    "technical report": "report",
    "research report": "report",
    "dataset": "dataset",
    "preprint": "posted-content",
    "review": "journal-article",
    "monograph": "monograph",
}

FETCH_TIMEOUT = 15


def _get_dc_values(metadata: list[dict], key: str) -> list[str]:
    """Pobierz wszystkie wartości dla klucza DC z metadanych."""
    return [m["value"] for m in metadata if m.get("key") == key and m.get("value")]


def _get_dc_value(metadata: list[dict], key: str) -> str | None:
    """Pobierz pierwszą wartość dla klucza DC."""
    values = _get_dc_values(metadata, key)
    return values[0] if values else None


def _parse_dspace_authors(
    metadata: list[dict],
) -> list[dict]:
    """Parsuj autorów z dc.contributor.author.

    Format DSpace: "Nazwisko, Imię" lub "Imię Nazwisko".
    """
    authors = []
    for name in _get_dc_values(metadata, "dc.contributor.author"):
        name = name.strip()
        if not name:
            continue

        if "," in name:
            parts = name.split(",", 1)
            family = parts[0].strip()
            given = parts[1].strip() if len(parts) > 1 else ""
        else:
            parts = name.rsplit(None, 1)
            if len(parts) == 2:
                given = parts[0].strip()
                family = parts[1].strip()
            else:
                family = parts[0].strip()
                given = ""

        authors.append({"family": family, "given": given, "orcid": ""})
    return authors


def _parse_year(date_str: str | None) -> int | None:
    """Wyciągnij rok z daty (np. "2018", "2018-05-15")."""
    if not date_str:
        return None
    match = re.search(r"\d{4}", date_str)
    return int(match.group()) if match else None


def _normalize_metadata(
    metadata: dict | list,
) -> list[dict]:
    """Normalize DSpace metadata to flat list.

    DSpace 7 may return metadata as:
    - dict: {key: [{value: ...}]} or dict: {key: "value"}
    - list: [{key, value}]
    """
    if isinstance(metadata, dict):
        flat = []
        for key, values in metadata.items():
            if isinstance(values, list):
                for v in values:
                    if isinstance(v, dict):
                        flat.append(
                            {
                                "key": key,
                                "value": v.get("value", ""),
                            }
                        )
            elif isinstance(values, str):
                flat.append({"key": key, "value": values})
        return flat
    return metadata


def _extract_doi(metadata: list[dict]) -> str | None:
    """Extract and clean DOI from metadata.

    Removes common URL prefixes and "DOI " text prefix.
    """
    doi_raw = _get_dc_value(metadata, "dc.identifier.doi")
    if not doi_raw:
        return None

    doi = doi_raw.strip()

    # Strip "DOI " text prefix (DSpace 6)
    if doi.upper().startswith("DOI "):
        doi = doi[4:].strip()

    for prefix in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
    ):
        if doi.lower().startswith(prefix.lower()):
            doi = doi[len(prefix) :]
            break
    return doi


def _extract_volume_issue_pages(
    metadata: list[dict],
) -> tuple[str | None, str | None, str | None]:
    """Wyciągnij volume, issue, pages z metadanych DC.

    Próbuje dedykowanych pól bibliographicCitation,
    potem fallback do parsowania citation string.
    """
    volume = _get_dc_value(metadata, "dc.bibliographicCitation.volume")
    issue = _get_dc_value(metadata, "dc.bibliographicCitation.issue")

    start_page = _get_dc_value(metadata, "dc.bibliographicCitation.startPage")
    end_page = _get_dc_value(metadata, "dc.bibliographicCitation.endPage")

    pages = None
    if start_page:
        pages = f"{start_page}-{end_page}" if end_page else start_page

    # Fallback: parsowanie citation string
    if not volume and not issue and not pages:
        citation = _get_dc_value(metadata, "dc.identifier.citation")
        if citation:
            volume, issue, pages = _parse_citation_string(citation)

    return volume, issue, pages


def _parse_citation_string(
    citation: str,
) -> tuple[str | None, str | None, str | None]:
    """Parse volume, issue, pages from a citation string.

    Supports formats:
    - "Vol. 42, No. 3, pp. 100-115"
    - "2025 vol. 33 s.195 - 205" (Polish)
    """
    volume = None
    issue = None
    pages = None

    vol_match = re.search(r"[Vv]ol\.?\s*(\d+)", citation)
    if vol_match:
        volume = vol_match.group(1)

    issue_match = re.search(
        r"[Nn]o\.?\s*(\d+)|[Ii]ss(?:ue)?\.?\s*(\d+)",
        citation,
    )
    if issue_match:
        issue = issue_match.group(1) or issue_match.group(2)

    # Standard: pp. or p.
    pages_match = re.search(r"[Pp]p?\.?\s*(\d+)\s*[-–]\s*(\d+)", citation)
    if pages_match:
        pages = f"{pages_match.group(1)}-{pages_match.group(2)}"

    # Polish: s.195 - 205
    if not pages:
        pages_match = re.search(r"[Ss]\.?\s*(\d+)\s*[-–]\s*(\d+)", citation)
        if pages_match:
            pages = f"{pages_match.group(1)}-{pages_match.group(2)}"

    return volume, issue, pages


def _resolve_url(metadata: list[dict]) -> str | None:
    """Resolve best URL from DSpace metadata.

    If dc.identifier.uri looks like a DOI (not an HTTP URL),
    fall back to dc.identifier (no qualifier) which often
    contains the handle URL.
    """
    uri = _get_dc_value(metadata, "dc.identifier.uri")
    if uri and uri.startswith("http"):
        return uri

    # Fallback: dc.identifier (no qualifier)
    plain = _get_dc_value(metadata, "dc.identifier")
    if plain and plain.startswith("http"):
        return plain

    return uri  # may be None or non-URL


def _build_extra_data(
    metadata: list[dict],
    citation_key: str = "dc.identifier.citation",
) -> dict:
    """Build extra data dictionary from metadata fields.

    Args:
        metadata: Flat list of DC metadata dicts.
        citation_key: Key for the citation field
            (differs between DSpace versions).
    """
    extra = {}

    alt_title = _get_dc_value(metadata, "dc.title.alternative")
    if alt_title:
        extra["alternative_title"] = alt_title

    handle = _get_dc_value(metadata, "dc.identifier.uri")
    if handle:
        extra["handle_url"] = handle

    citation = _get_dc_value(metadata, citation_key)
    if citation:
        extra["citation"] = citation

    return extra
