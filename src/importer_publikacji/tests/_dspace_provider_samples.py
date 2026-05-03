"""Sample DSpace 6/7 REST responses for ``DSpaceProvider`` tests.

Shared between ``test_dspace_provider*.py`` modules. Not a pytest module
(leading underscore + no ``test_`` prefix) — pytest won't collect it.
"""

from unittest.mock import MagicMock

SAMPLE_UUID = "276895f0-2d8a-4d99-8e45-8c9bc891da24"
BASE_URL = "https://repozytorium.wsb-nlu.edu.pl"
SAMPLE_URL = f"{BASE_URL}/items/{SAMPLE_UUID}"

# Przykładowa odpowiedź DSpace 7 REST API (metadata jako dict)
SAMPLE_DSPACE_RESPONSE = {
    "uuid": SAMPLE_UUID,
    "name": "Przykładowa publikacja naukowa",
    "metadata": {
        "dc.title": [{"value": "Przykładowa publikacja naukowa"}],
        "dc.contributor.author": [
            {"value": "Kowalski, Jan"},
            {"value": "Nowak, Anna Maria"},
        ],
        "dc.date.issued": [{"value": "2020-05-15"}],
        "dc.identifier.doi": [{"value": "https://doi.org/10.1234/test.2020"}],
        "dc.relation.ispartof": [{"value": "Journal of Testing"}],
        "dc.identifier.issn": [{"value": "1234-5678"}],
        "dc.identifier.isbn": [{"value": "978-3-16-148410-0"}],
        "dc.publisher": [{"value": "Academic Press"}],
        "dc.type": [{"value": "article"}],
        "dc.language.iso": [{"value": "pl"}],
        "dc.description.abstract": [{"value": "To jest abstrakt."}],
        "dc.bibliographicCitation.volume": [{"value": "42"}],
        "dc.bibliographicCitation.issue": [{"value": "3"}],
        "dc.bibliographicCitation.startPage": [{"value": "100"}],
        "dc.bibliographicCitation.endPage": [{"value": "115"}],
        "dc.identifier.uri": [{"value": "https://repo.example.com/handle/123/456"}],
        "dc.rights.uri": [{"value": ("https://creativecommons.org/licenses/by/4.0/")}],
        "dc.subject": [
            {"value": "nauka"},
            {"value": "testowanie"},
        ],
        "dc.title.alternative": [{"value": "Alternative Title"}],
        "dc.identifier.citation": [
            {"value": ("J. Testing, Vol. 42, No. 3, pp. 100-115")}
        ],
    },
}

# Metadane w formacie listy (starszy format DSpace)
SAMPLE_DSPACE_LIST_METADATA = {
    "uuid": SAMPLE_UUID,
    "name": "Publikacja z listą",
    "metadata": [
        {"key": "dc.title", "value": "Tytuł z listy"},
        {
            "key": "dc.contributor.author",
            "value": "Nowak, Piotr",
        },
        {"key": "dc.date.issued", "value": "2019"},
        {"key": "dc.type", "value": "book"},
    ],
}

# Przykładowa odpowiedź DSpace 6 REST API
SAMPLE_DSPACE6_RESPONSE = {
    "id": 922,
    "name": "Artykuł naukowy z DSpace 6",
    "handle": "123456789/922",
    "type": "item",
    "metadata": [
        {
            "key": "dc.title",
            "value": "Artykuł naukowy z DSpace 6",
        },
        {
            "key": "dc.contributor.author",
            "value": "Kowalska, Maria",
        },
        {
            "key": "dc.contributor.author",
            "value": "Wiśniewski, Tomasz",
        },
        {"key": "dc.date.issued", "value": "2025"},
        {
            "key": "dc.identifier.doi",
            "value": "DOI 10.2478/jvetres-2025-0001",
        },
        {
            "key": "dcterms.title",
            "value": "Journal of Veterinary Research",
        },
        {
            "key": "dcterms.bibliographicCitation",
            "value": "2025 vol. 33 s.195 - 205",
        },
        {"key": "dc.type", "value": "article"},
        {"key": "dc.language.iso", "value": "en"},
        {
            "key": "dc.description.abstract",
            "value": "Abstrakt artykułu.",
        },
        {
            "key": "dc.identifier.uri",
            "value": ("https://dspace.piwet.pulawy.pl/handle/123456789/922"),
        },
        {"key": "dc.publisher", "value": "Sciendo"},
        {"key": "dc.subject", "value": "veterinary"},
    ],
}

SAMPLE_HANDLE_URL = "https://dspace.piwet.pulawy.pl/handle/123456789/922"


def _flat_metadata(dspace_dict_metadata: dict) -> list[dict]:
    """Konwertuj metadata dict na flat list."""
    flat = []
    for key, values in dspace_dict_metadata.items():
        for v in values:
            flat.append({"key": key, "value": v["value"]})
    return flat


FLAT_META = _flat_metadata(SAMPLE_DSPACE_RESPONSE["metadata"])


def _mock_response(json_data, status_code=200):
    """Build a ``requests``-like mock response."""
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = __import__(
            "requests"
        ).exceptions.HTTPError()
    return resp
