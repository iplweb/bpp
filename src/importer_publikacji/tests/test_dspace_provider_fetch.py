"""End-to-end ``DSpaceProvider.fetch`` tests with mocked HTTP.

Covers DSpace 7 (REST ``/server/api/core/items/<uuid>``) and DSpace 6
(REST ``/rest/handle/<handle>?expand=metadata``) success/error paths,
DOI cleanup, source-title resolution and URL fallback when
``dc.identifier.uri`` is itself a DOI. See ``test_dspace_provider``
module docstring for the full split layout.
"""

from unittest.mock import patch

import pytest

from importer_publikacji.providers.dspace import DSpaceProvider

from ._dspace_provider_samples import (
    BASE_URL,
    SAMPLE_DSPACE6_RESPONSE,
    SAMPLE_DSPACE_LIST_METADATA,
    SAMPLE_DSPACE_RESPONSE,
    SAMPLE_HANDLE_URL,
    SAMPLE_URL,
    SAMPLE_UUID,
    _mock_response,
)

# DSpace fetch idzie teraz przez wspólny safe_get (guard SSRF w
# providers.www.network). safe_get woła requests.get z network.requests
# (ten sam globalny moduł), więc patchujemy get właśnie tam.
_REQUESTS_GET = "importer_publikacji.providers.www.network.requests.get"


@pytest.fixture(autouse=True)
def _bypass_ssrf_host_check(monkeypatch):
    """Te testy weryfikują PARSOWANIE metadanych DSpace, nie guard SSRF (ten
    jest pokryty w test_dspace_provider_ssrf.py). safe_get waliduje host przez
    DNS — pozwalamy mu przejść, aby fake-hosty próbek nie były blokowane."""
    from importer_publikacji.providers.www import network

    monkeypatch.setattr(network, "_host_is_safe", lambda hostname: True)


# --- Full fetch DSpace 7 (mocked HTTP) ---


@patch(_REQUESTS_GET)
def test_fetch_dspace7_success(mock_get):
    mock_get.return_value = _mock_response(SAMPLE_DSPACE_RESPONSE)

    p = DSpaceProvider()
    pub = p.fetch(SAMPLE_URL)

    assert pub is not None
    assert pub.title == "Przykładowa publikacja naukowa"
    assert pub.doi == "10.1234/test.2020"
    assert pub.year == 2020
    assert len(pub.authors) == 2
    assert pub.authors[0]["family"] == "Kowalski"
    assert pub.authors[0]["given"] == "Jan"
    assert pub.authors[1]["family"] == "Nowak"
    assert pub.authors[1]["given"] == "Anna Maria"
    assert pub.source_title == "Journal of Testing"
    assert pub.issn == "1234-5678"
    assert pub.isbn == "978-3-16-148410-0"
    assert pub.publisher == "Academic Press"
    assert pub.publication_type == "journal-article"
    assert pub.language == "pl"
    assert pub.abstract == "To jest abstrakt."
    assert pub.volume == "42"
    assert pub.issue == "3"
    assert pub.pages == "100-115"
    assert pub.url == ("https://repo.example.com/handle/123/456")
    assert "creativecommons.org" in pub.license_url
    assert pub.keywords == ["nauka", "testowanie"]
    assert pub.extra["alternative_title"] == "Alternative Title"
    assert pub.extra["handle_url"] == ("https://repo.example.com/handle/123/456")

    mock_get.assert_called_once_with(
        f"{BASE_URL}/server/api/core/items/{SAMPLE_UUID}",
        timeout=15,
        allow_redirects=False,
        headers=None,
    )


@patch(_REQUESTS_GET)
def test_fetch_list_metadata_format(mock_get):
    mock_get.return_value = _mock_response(SAMPLE_DSPACE_LIST_METADATA)

    p = DSpaceProvider()
    pub = p.fetch(SAMPLE_URL)

    assert pub is not None
    assert pub.title == "Tytuł z listy"
    assert len(pub.authors) == 1
    assert pub.authors[0]["family"] == "Nowak"
    assert pub.year == 2019
    assert pub.publication_type == "book"


@patch("importer_publikacji.providers.dspace._fallback_to_www", return_value=None)
@patch(_REQUESTS_GET)
def test_fetch_http_error(mock_get, mock_fallback):
    mock_get.return_value = _mock_response({}, status_code=404)

    p = DSpaceProvider()
    pub = p.fetch(SAMPLE_URL)
    assert pub is None
    # WWW fallback został wywołany (zwrócił None — provider nie obronił).
    mock_fallback.assert_called_once_with(SAMPLE_URL)


@patch("importer_publikacji.providers.dspace._fallback_to_www", return_value=None)
@patch(_REQUESTS_GET)
def test_fetch_connection_error(mock_get, mock_fallback):
    mock_get.side_effect = __import__("requests").exceptions.ConnectionError()

    p = DSpaceProvider()
    pub = p.fetch(SAMPLE_URL)
    assert pub is None
    mock_fallback.assert_called_once_with(SAMPLE_URL)


@patch("importer_publikacji.providers.dspace._fallback_to_www", return_value=None)
@patch(_REQUESTS_GET)
def test_fetch_no_title(mock_get, mock_fallback):
    data = {
        "uuid": SAMPLE_UUID,
        "metadata": {
            "dc.contributor.author": [{"value": "Kowalski, Jan"}],
        },
    }
    mock_get.return_value = _mock_response(data)

    p = DSpaceProvider()
    pub = p.fetch(SAMPLE_URL)
    assert pub is None
    mock_fallback.assert_called_once_with(SAMPLE_URL)


@patch("importer_publikacji.providers.dspace._fallback_to_www")
@patch(_REQUESTS_GET)
def test_fetch_falls_back_to_www_when_api_fails(mock_get, mock_fallback):
    """DSpace API failure → WWW provider próbuje sparsować HTML."""
    from importer_publikacji.providers import FetchedPublication

    mock_get.return_value = _mock_response({}, status_code=503)
    mock_fallback.return_value = FetchedPublication(
        raw_data={"url": SAMPLE_URL},
        title="Tytuł ze strony WWW",
        doi="10.1234/from-www",
        year=2024,
        authors=[{"family": "Kowalski", "given": "Jan", "orcid": ""}],
        url=SAMPLE_URL,
    )

    pub = DSpaceProvider().fetch(SAMPLE_URL)
    assert pub is not None
    assert pub.title == "Tytuł ze strony WWW"
    assert pub.doi == "10.1234/from-www"
    mock_fallback.assert_called_once_with(SAMPLE_URL)


@patch("importer_publikacji.providers.dspace._fallback_to_www")
@patch(_REQUESTS_GET)
def test_fetch_does_not_fall_back_when_api_succeeds(mock_get, mock_fallback):
    """Gdy DSpace API zwraca dane, WWW fallback NIE jest wywoływany."""
    mock_get.return_value = _mock_response(SAMPLE_DSPACE_RESPONSE)

    pub = DSpaceProvider().fetch(SAMPLE_URL)
    assert pub is not None
    mock_fallback.assert_not_called()


def test_fetch_invalid_url():
    p = DSpaceProvider()
    pub = p.fetch("not a valid url")
    assert pub is None


@patch(_REQUESTS_GET)
def test_fetch_doi_cleanup(mock_get):
    """DOI z prefiksem URL powinien być oczyszczony."""
    data = {
        "uuid": SAMPLE_UUID,
        "metadata": {
            "dc.title": [{"value": "Test"}],
            "dc.identifier.doi": [{"value": "https://doi.org/10.5555/test"}],
        },
    }
    mock_get.return_value = _mock_response(data)

    p = DSpaceProvider()
    pub = p.fetch(SAMPLE_URL)
    assert pub is not None
    assert pub.doi == "10.5555/test"


@patch(_REQUESTS_GET)
def test_fetch_minimal_metadata(mock_get):
    """Minimalne metadane — tylko tytuł."""
    data = {
        "uuid": SAMPLE_UUID,
        "metadata": {
            "dc.title": [{"value": "Tylko tytuł"}],
        },
    }
    mock_get.return_value = _mock_response(data)

    p = DSpaceProvider()
    pub = p.fetch(SAMPLE_URL)
    assert pub is not None
    assert pub.title == "Tylko tytuł"
    assert pub.authors == []
    assert pub.year is None
    assert pub.doi is None
    assert pub.volume is None
    assert pub.keywords == []


@patch(_REQUESTS_GET)
def test_fetch_unknown_type(mock_get):
    """Nieznany typ → publication_type = None."""
    data = {
        "uuid": SAMPLE_UUID,
        "metadata": {
            "dc.title": [{"value": "Test"}],
            "dc.type": [{"value": "Some Unknown Type"}],
        },
    }
    mock_get.return_value = _mock_response(data)

    p = DSpaceProvider()
    pub = p.fetch(SAMPLE_URL)
    assert pub is not None
    assert pub.publication_type is None


# --- Full fetch DSpace 6 (mocked HTTP) ---


@patch(_REQUESTS_GET)
def test_fetch_dspace6_success(mock_get):
    mock_get.return_value = _mock_response(SAMPLE_DSPACE6_RESPONSE)

    p = DSpaceProvider()
    pub = p.fetch(SAMPLE_HANDLE_URL)

    assert pub is not None
    assert pub.title == "Artykuł naukowy z DSpace 6"
    assert pub.doi == "10.2478/jvetres-2025-0001"
    assert pub.year == 2025
    assert len(pub.authors) == 2
    assert pub.authors[0]["family"] == "Kowalska"
    assert pub.authors[0]["given"] == "Maria"
    assert pub.authors[1]["family"] == "Wiśniewski"
    assert pub.authors[1]["given"] == "Tomasz"
    assert pub.source_title == "Journal of Veterinary Research"
    assert pub.publisher == "Sciendo"
    assert pub.publication_type == "journal-article"
    assert pub.language == "en"
    assert pub.abstract == "Abstrakt artykułu."
    assert pub.volume == "33"
    assert pub.pages == "195-205"
    assert pub.keywords == ["veterinary"]

    mock_get.assert_called_once_with(
        "https://dspace.piwet.pulawy.pl/rest/handle/123456789/922?expand=metadata",
        timeout=15,
        allow_redirects=False,
        headers=None,
    )


@patch(_REQUESTS_GET)
def test_fetch_dspace6_doi_text_prefix(mock_get):
    """DOI z prefiksem 'DOI ' powinien być oczyszczony."""
    data = {
        "metadata": [
            {"key": "dc.title", "value": "Test"},
            {
                "key": "dc.identifier.doi",
                "value": "DOI 10.2478/test",
            },
        ],
    }
    mock_get.return_value = _mock_response(data)

    p = DSpaceProvider()
    pub = p.fetch(SAMPLE_HANDLE_URL)
    assert pub is not None
    assert pub.doi == "10.2478/test"


@patch(_REQUESTS_GET)
def test_fetch_dspace6_dcterms_source_title(mock_get):
    """dcterms.title → source_title w DSpace 6."""
    data = {
        "metadata": [
            {"key": "dc.title", "value": "Artykuł"},
            {
                "key": "dcterms.title",
                "value": "Nazwa Czasopisma",
            },
        ],
    }
    mock_get.return_value = _mock_response(data)

    p = DSpaceProvider()
    pub = p.fetch(SAMPLE_HANDLE_URL)
    assert pub is not None
    assert pub.source_title == "Nazwa Czasopisma"


@patch(_REQUESTS_GET)
def test_fetch_dspace6_relation_over_dcterms(mock_get):
    """dc.relation.ispartof ma priorytet nad dcterms.title."""
    data = {
        "metadata": [
            {"key": "dc.title", "value": "Artykuł"},
            {
                "key": "dc.relation.ispartof",
                "value": "Primary Journal",
            },
            {
                "key": "dcterms.title",
                "value": "Fallback Journal",
            },
        ],
    }
    mock_get.return_value = _mock_response(data)

    p = DSpaceProvider()
    pub = p.fetch(SAMPLE_HANDLE_URL)
    assert pub is not None
    assert pub.source_title == "Primary Journal"


@patch(_REQUESTS_GET)
def test_fetch_dspace6_http_error(mock_get):
    mock_get.return_value = _mock_response({}, status_code=404)

    p = DSpaceProvider()
    pub = p.fetch(SAMPLE_HANDLE_URL)
    assert pub is None


@patch(_REQUESTS_GET)
def test_fetch_dspace6_connection_error(mock_get):
    mock_get.side_effect = __import__("requests").exceptions.ConnectionError()

    p = DSpaceProvider()
    pub = p.fetch(SAMPLE_HANDLE_URL)
    assert pub is None


@patch("importer_publikacji.providers.dspace._fallback_to_www", return_value=None)
@patch(_REQUESTS_GET)
def test_fetch_dspace6_no_title(mock_get, mock_fallback):
    data = {
        "metadata": [
            {
                "key": "dc.contributor.author",
                "value": "Kowalski, Jan",
            },
        ],
    }
    mock_get.return_value = _mock_response(data)

    p = DSpaceProvider()
    pub = p.fetch(SAMPLE_HANDLE_URL)
    assert pub is None
    mock_fallback.assert_called_once_with(SAMPLE_HANDLE_URL)


@patch(_REQUESTS_GET)
def test_fetch_dspace6_citation_parsing(mock_get):
    """dcterms.bibliographicCitation parsing."""
    data = {
        "metadata": [
            {"key": "dc.title", "value": "Test"},
            {
                "key": "dcterms.bibliographicCitation",
                "value": "2025 vol. 33 s.195 - 205",
            },
        ],
    }
    mock_get.return_value = _mock_response(data)

    p = DSpaceProvider()
    pub = p.fetch(SAMPLE_HANDLE_URL)
    assert pub is not None
    assert pub.volume == "33"
    assert pub.pages == "195-205"


# --- DSpace 7 fetch with DOI in dc.identifier.uri ---


@patch(_REQUESTS_GET)
def test_fetch_dspace7_url_fallback_doi_in_uri(mock_get):
    """DSpace 7: dc.identifier.uri = DOI
    → url z dc.identifier."""
    data = {
        "uuid": SAMPLE_UUID,
        "metadata": {
            "dc.title": [{"value": "Test DOI URL"}],
            "dc.identifier.uri": [{"value": "10.1234/test.2020"}],
            "dc.identifier": [{"value": ("https://hdl.handle.net/123/456")}],
        },
    }
    mock_get.return_value = _mock_response(data)

    p = DSpaceProvider()
    pub = p.fetch(SAMPLE_URL)
    assert pub is not None
    assert pub.url == ("https://hdl.handle.net/123/456")
