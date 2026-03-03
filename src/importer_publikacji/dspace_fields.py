"""Kategoryzacja pól DC z metadanych DSpace."""

from importer_publikacji.providers.dspace_common import (
    _normalize_metadata,
)

# Pola DC odczytywane przez provider DSpace
EXTRACTED_KEYS = {
    "dc.title",
    "dc.contributor.author",
    "dc.date.issued",
    "dc.identifier.doi",
    "dc.identifier.issn",
    "dc.identifier.isbn",
    "dc.identifier.uri",
    "dc.identifier.citation",
    "dc.publisher",
    "dc.type",
    "dc.language.iso",
    "dc.description.abstract",
    "dc.subject",
    "dc.rights.uri",
    "dc.relation.ispartof",
    "dc.bibliographicCitation.volume",
    "dc.bibliographicCitation.issue",
    "dc.bibliographicCitation.startPage",
    "dc.bibliographicCitation.endPage",
    "dc.title.alternative",
    "dcterms.bibliographicCitation",
    "dcterms.title",
    "dc.identifier",
}

# Pola DC znane, ale nieużywane bezpośrednio
IGNORED_KEYS = {
    "dc.date.accessioned",
    "dc.date.available",
    "dc.description.provenance",
    "dc.description.sponsorship",
    "dc.format",
    "dc.format.extent",
    "dc.format.mimetype",
    "dc.coverage.spatial",
    "dc.coverage.temporal",
    "dc.rights",
    "dc.source",
}


def categorize_dspace_fields(raw_data: dict) -> dict:
    """Kategoryzuj pola DC z metadanych DSpace.

    Zwraca {"wyodrebnione": [...], "ignorowane": [...],
    "obce": [...]} gdzie każda lista to posortowane
    (key, value) tuples.
    """
    if not raw_data or not isinstance(raw_data, dict):
        return {
            "wyodrebnione": [],
            "ignorowane": [],
            "obce": [],
        }

    metadata = raw_data.get("metadata", [])
    if not metadata:
        return {
            "wyodrebnione": [],
            "ignorowane": [],
            "obce": [],
        }

    metadata = _normalize_metadata(metadata)

    wyodrebnione = []
    ignorowane = []
    obce = []

    for entry in metadata:
        key = entry.get("key", "")
        value = entry.get("value", "")
        if not key:
            continue

        item = (key, value)
        if key in EXTRACTED_KEYS:
            wyodrebnione.append(item)
        elif key in IGNORED_KEYS:
            ignorowane.append(item)
        else:
            obce.append(item)

    wyodrebnione.sort()
    ignorowane.sort()
    obce.sort()

    return {
        "wyodrebnione": wyodrebnione,
        "ignorowane": ignorowane,
        "obce": obce,
    }
