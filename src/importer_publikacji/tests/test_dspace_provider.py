from unittest.mock import MagicMock, patch

from importer_publikacji.providers import (
    InputMode,
    get_available_providers,
    get_provider,
)
from importer_publikacji.providers.dspace import (
    DSpaceProvider,
    _parse_dspace7_url,
    _parse_dspace_url,
    _parse_handle_url,
)
from importer_publikacji.providers.dspace_common import (
    DSPACE_TYPE_MAP,
    _extract_volume_issue_pages,
    _get_dc_value,
    _get_dc_values,
    _parse_citation_string,
    _parse_dspace_authors,
    _parse_year,
    _resolve_url,
)

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


# --- Registration ---


def test_dspace_provider_registered():
    providers = get_available_providers()
    assert "DSpace" in providers


def test_dspace_provider_name():
    p = DSpaceProvider()
    assert p.name == "DSpace"
    assert p.identifier_label == "Adres strony WWW w repozytorium DSpace"


def test_dspace_provider_input_mode():
    p = DSpaceProvider()
    assert p.input_mode == InputMode.IDENTIFIER


def test_get_provider_dspace():
    p = get_provider("DSpace")
    assert isinstance(p, DSpaceProvider)


# --- DSpace 7 URL parsing ---


def test_parse_url_valid():
    result = _parse_dspace7_url(SAMPLE_URL)
    assert result == (BASE_URL, SAMPLE_UUID)


def test_parse_url_with_full():
    url = f"{BASE_URL}/items/{SAMPLE_UUID}/full"
    result = _parse_dspace7_url(url)
    assert result == (BASE_URL, SAMPLE_UUID)


def test_parse_url_trailing_slash():
    url = f"{BASE_URL}/items/{SAMPLE_UUID}/"
    result = _parse_dspace7_url(url)
    assert result == (BASE_URL, SAMPLE_UUID)


def test_parse_url_no_scheme():
    url = f"repozytorium.wsb-nlu.edu.pl/items/{SAMPLE_UUID}"
    result = _parse_dspace7_url(url)
    assert result is not None
    assert result[1] == SAMPLE_UUID
    assert result[0] == "https://repozytorium.wsb-nlu.edu.pl"


def test_parse_url_invalid_uuid():
    url = f"{BASE_URL}/items/not-a-valid-uuid"
    assert _parse_dspace7_url(url) is None


def test_parse_url_no_items():
    url = f"{BASE_URL}/handle/123/456"
    assert _parse_dspace7_url(url) is None


def test_parse_url_empty():
    assert _parse_dspace7_url("") is None
    assert _parse_dspace7_url("   ") is None


# --- DSpace 6 handle URL parsing ---


def test_parse_handle_url_valid():
    result = _parse_handle_url(SAMPLE_HANDLE_URL)
    assert result == (
        "https://dspace.piwet.pulawy.pl",
        "123456789/922",
    )


def test_parse_handle_url_trailing_slash():
    url = "https://dspace.piwet.pulawy.pl/handle/123456789/922/"
    result = _parse_handle_url(url)
    assert result == (
        "https://dspace.piwet.pulawy.pl",
        "123456789/922",
    )


def test_parse_handle_url_no_scheme():
    url = "dspace.piwet.pulawy.pl/handle/123456789/922"
    result = _parse_handle_url(url)
    assert result is not None
    assert result[1] == "123456789/922"
    assert result[0] == "https://dspace.piwet.pulawy.pl"


def test_parse_handle_url_xmlui_prefix():
    url = "https://repo.example.com/xmlui/handle/123/456"
    result = _parse_handle_url(url)
    assert result == (
        "https://repo.example.com",
        "123/456",
    )


def test_parse_handle_url_no_handle():
    url = "https://repo.example.com/items/some-uuid"
    assert _parse_handle_url(url) is None


def test_parse_handle_url_empty():
    assert _parse_handle_url("") is None
    assert _parse_handle_url("   ") is None


# --- Autodetection (_parse_dspace_url) ---


def test_autodetect_dspace7():
    result = _parse_dspace_url(SAMPLE_URL)
    assert result is not None
    base_url, ident, version = result
    assert version == "7"
    assert ident == SAMPLE_UUID


def test_autodetect_dspace6():
    result = _parse_dspace_url(SAMPLE_HANDLE_URL)
    assert result is not None
    base_url, ident, version = result
    assert version == "6"
    assert ident == "123456789/922"


def test_autodetect_invalid():
    assert _parse_dspace_url("not a url") is None


# --- validate_identifier ---


def test_validate_identifier_dspace7():
    p = DSpaceProvider()
    result = p.validate_identifier(SAMPLE_URL)
    assert result == f"{BASE_URL}/items/{SAMPLE_UUID}"


def test_validate_identifier_dspace7_with_full():
    p = DSpaceProvider()
    url = f"{BASE_URL}/items/{SAMPLE_UUID}/full"
    result = p.validate_identifier(url)
    assert result == f"{BASE_URL}/items/{SAMPLE_UUID}"


def test_validate_identifier_dspace6():
    p = DSpaceProvider()
    result = p.validate_identifier(SAMPLE_HANDLE_URL)
    assert result == ("https://dspace.piwet.pulawy.pl/handle/123456789/922")


def test_validate_identifier_invalid():
    p = DSpaceProvider()
    assert p.validate_identifier("not a url") is None
    assert p.validate_identifier("") is None


# --- DC value helpers ---


def test_get_dc_value_existing():
    assert _get_dc_value(FLAT_META, "dc.title") == "Przykładowa publikacja naukowa"


def test_get_dc_value_missing():
    assert _get_dc_value(FLAT_META, "dc.nonexistent") is None


def test_get_dc_values_multiple():
    values = _get_dc_values(FLAT_META, "dc.subject")
    assert values == ["nauka", "testowanie"]


def test_get_dc_values_empty():
    assert _get_dc_values(FLAT_META, "dc.nonexistent") == []


# --- Author parsing ---


def test_parse_authors_surname_given():
    meta = [
        {
            "key": "dc.contributor.author",
            "value": "Kowalski, Jan",
        },
        {
            "key": "dc.contributor.author",
            "value": "Nowak, Anna Maria",
        },
    ]
    result = _parse_dspace_authors(meta)
    assert len(result) == 2
    assert result[0] == {
        "family": "Kowalski",
        "given": "Jan",
        "orcid": "",
    }
    assert result[1] == {
        "family": "Nowak",
        "given": "Anna Maria",
        "orcid": "",
    }


def test_parse_authors_no_comma():
    meta = [
        {
            "key": "dc.contributor.author",
            "value": "Jan Kowalski",
        }
    ]
    result = _parse_dspace_authors(meta)
    assert len(result) == 1
    assert result[0]["family"] == "Kowalski"
    assert result[0]["given"] == "Jan"


def test_parse_authors_single_name():
    meta = [
        {
            "key": "dc.contributor.author",
            "value": "Kowalski",
        }
    ]
    result = _parse_dspace_authors(meta)
    assert len(result) == 1
    assert result[0]["family"] == "Kowalski"
    assert result[0]["given"] == ""


def test_parse_authors_empty():
    assert _parse_dspace_authors([]) == []


# --- Year parsing ---


def test_parse_year_simple():
    assert _parse_year("2020") == 2020


def test_parse_year_date():
    assert _parse_year("2020-05-15") == 2020


def test_parse_year_iso():
    assert _parse_year("2020-05-15T10:30:00Z") == 2020


def test_parse_year_empty():
    assert _parse_year("") is None
    assert _parse_year(None) is None


# --- Volume/issue/pages extraction ---


def test_extract_explicit_fields():
    meta = [
        {
            "key": "dc.bibliographicCitation.volume",
            "value": "42",
        },
        {
            "key": "dc.bibliographicCitation.issue",
            "value": "3",
        },
        {
            "key": "dc.bibliographicCitation.startPage",
            "value": "100",
        },
        {
            "key": "dc.bibliographicCitation.endPage",
            "value": "115",
        },
    ]
    vol, iss, pages = _extract_volume_issue_pages(meta)
    assert vol == "42"
    assert iss == "3"
    assert pages == "100-115"


def test_extract_start_page_only():
    meta = [
        {
            "key": "dc.bibliographicCitation.startPage",
            "value": "50",
        },
    ]
    vol, iss, pages = _extract_volume_issue_pages(meta)
    assert pages == "50"


def test_extract_citation_fallback():
    meta = [
        {
            "key": "dc.identifier.citation",
            "value": ("J. Testing, Vol. 10, No. 2, pp. 50-60"),
        }
    ]
    vol, iss, pages = _extract_volume_issue_pages(meta)
    assert vol == "10"
    assert iss == "2"
    assert pages == "50-60"


def test_extract_citation_issue_format():
    meta = [
        {
            "key": "dc.identifier.citation",
            "value": "Journal, Vol. 5, Issue 8",
        }
    ]
    vol, iss, pages = _extract_volume_issue_pages(meta)
    assert vol == "5"
    assert iss == "8"
    assert pages is None


def test_extract_empty():
    vol, iss, pages = _extract_volume_issue_pages([])
    assert vol is None
    assert iss is None
    assert pages is None


# --- Citation string parsing (Polish format) ---


def test_parse_citation_polish_format():
    vol, iss, pages = _parse_citation_string("2025 vol. 33 s.195 - 205")
    assert vol == "33"
    assert pages == "195-205"


def test_parse_citation_standard_format():
    vol, iss, pages = _parse_citation_string("J. Testing, Vol. 10, No. 2, pp. 50-60")
    assert vol == "10"
    assert iss == "2"
    assert pages == "50-60"


# --- Type mapping ---


def test_type_map_article():
    assert DSPACE_TYPE_MAP["article"] == "journal-article"


def test_type_map_book():
    assert DSPACE_TYPE_MAP["book"] == "book"


def test_type_map_book_chapter():
    assert DSPACE_TYPE_MAP["book chapter"] == "book-chapter"


def test_type_map_thesis():
    assert DSPACE_TYPE_MAP["doctoral thesis"] == "dissertation"


def test_type_map_unknown():
    assert DSPACE_TYPE_MAP.get("unknown type") is None


# --- Full fetch DSpace 7 (mocked HTTP) ---


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = __import__(
            "requests"
        ).exceptions.HTTPError()
    return resp


@patch("importer_publikacji.providers.dspace.requests.get")
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
    )


@patch("importer_publikacji.providers.dspace.requests.get")
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


@patch("importer_publikacji.providers.dspace.requests.get")
def test_fetch_http_error(mock_get):
    mock_get.return_value = _mock_response({}, status_code=404)

    p = DSpaceProvider()
    pub = p.fetch(SAMPLE_URL)
    assert pub is None


@patch("importer_publikacji.providers.dspace.requests.get")
def test_fetch_connection_error(mock_get):
    mock_get.side_effect = __import__("requests").exceptions.ConnectionError()

    p = DSpaceProvider()
    pub = p.fetch(SAMPLE_URL)
    assert pub is None


@patch("importer_publikacji.providers.dspace.requests.get")
def test_fetch_no_title(mock_get):
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


def test_fetch_invalid_url():
    p = DSpaceProvider()
    pub = p.fetch("not a valid url")
    assert pub is None


@patch("importer_publikacji.providers.dspace.requests.get")
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


@patch("importer_publikacji.providers.dspace.requests.get")
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


@patch("importer_publikacji.providers.dspace.requests.get")
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


@patch("importer_publikacji.providers.dspace.requests.get")
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
    )


@patch("importer_publikacji.providers.dspace.requests.get")
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


@patch("importer_publikacji.providers.dspace.requests.get")
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


@patch("importer_publikacji.providers.dspace.requests.get")
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


@patch("importer_publikacji.providers.dspace.requests.get")
def test_fetch_dspace6_http_error(mock_get):
    mock_get.return_value = _mock_response({}, status_code=404)

    p = DSpaceProvider()
    pub = p.fetch(SAMPLE_HANDLE_URL)
    assert pub is None


@patch("importer_publikacji.providers.dspace.requests.get")
def test_fetch_dspace6_connection_error(mock_get):
    mock_get.side_effect = __import__("requests").exceptions.ConnectionError()

    p = DSpaceProvider()
    pub = p.fetch(SAMPLE_HANDLE_URL)
    assert pub is None


@patch("importer_publikacji.providers.dspace.requests.get")
def test_fetch_dspace6_no_title(mock_get):
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


@patch("importer_publikacji.providers.dspace.requests.get")
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


# --- _resolve_url tests ---


def test_resolve_url_normal_http():
    """dc.identifier.uri z HTTP → użyj go."""
    meta = [
        {
            "key": "dc.identifier.uri",
            "value": "https://repo.example.com/handle/1/2",
        },
    ]
    assert _resolve_url(meta) == ("https://repo.example.com/handle/1/2")


def test_resolve_url_doi_fallback_to_dc_identifier():
    """dc.identifier.uri = DOI → użyj dc.identifier."""
    meta = [
        {
            "key": "dc.identifier.uri",
            "value": "10.1234/test.2020",
        },
        {
            "key": "dc.identifier",
            "value": "https://hdl.handle.net/123/456",
        },
    ]
    assert _resolve_url(meta) == ("https://hdl.handle.net/123/456")


def test_resolve_url_doi_no_fallback():
    """dc.identifier.uri = DOI, brak dc.identifier → DOI."""
    meta = [
        {
            "key": "dc.identifier.uri",
            "value": "10.1234/test.2020",
        },
    ]
    assert _resolve_url(meta) == "10.1234/test.2020"


def test_resolve_url_missing():
    """Brak dc.identifier.uri → None."""
    assert _resolve_url([]) is None


def test_resolve_url_dc_identifier_non_http():
    """dc.identifier.uri = DOI, dc.identifier nie-HTTP."""
    meta = [
        {
            "key": "dc.identifier.uri",
            "value": "10.1234/test",
        },
        {
            "key": "dc.identifier",
            "value": "some-local-id",
        },
    ]
    # dc.identifier nie jest HTTP,
    # więc zwraca oryginalny uri (DOI)
    assert _resolve_url(meta) == "10.1234/test"


# --- DSpace 7 fetch with DOI in dc.identifier.uri ---


@patch("importer_publikacji.providers.dspace.requests.get")
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
