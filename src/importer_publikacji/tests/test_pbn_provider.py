from unittest.mock import MagicMock, patch

import pytest

from importer_publikacji.providers import (
    get_available_providers,
    get_provider,
)
from importer_publikacji.providers.pbn import (
    PBN_TYPE_MAP,
    PBNProvider,
    _extract_abstract,
    _extract_authors,
    _extract_isbn,
    _extract_keywords,
    _extract_license_url,
    _extract_year,
    _get_current_version_object,
)
from pbn_api.exceptions import (
    AccessDeniedException,
    HttpException,
    PraceSerwisoweException,
)

SAMPLE_PBN_UID = "5e709189878c28a04737dc6f"

SAMPLE_PBN_ARTICLE = {
    "mongoId": SAMPLE_PBN_UID,
    "status": "ACTIVE",
    "verificationLevel": "VERIFIED",
    "verified": True,
    "versions": [
        {
            "current": True,
            "object": {
                "title": "Przykładowy artykuł naukowy",
                "doi": "10.1234/test.2020",
                "year": 2020,
                "type": "ARTICLE",
                "mainLanguage": "pol",
                "volume": "42",
                "issue": "3",
                "pagesFromTo": "100-115",
                "publicUri": "https://example.com/pub/123",
                "journal": {
                    "title": "Czasopismo Testowe",
                    "issn": "1234-5678",
                    "eissn": "9876-5432",
                    "publisher": "Wydawnictwo Testowe",
                },
                "authors": {
                    "aaa111bbb222ccc333ddd441": {
                        "lastName": "Kowalski",
                        "name": "Jan",
                    },
                    "aaa111bbb222ccc333ddd442": {
                        "lastName": "Nowak",
                        "name": "Anna",
                    },
                },
                "keywords": {
                    "pl": ["nauka", "testowanie"],
                    "en": ["science", "testing"],
                },
                "abstracts": {
                    "pl": "To jest abstrakt po polsku.",
                    "en": "This is an abstract.",
                },
                "openAccess": {
                    "license": "CC_BY",
                },
            },
        }
    ],
}

SAMPLE_PBN_BOOK = {
    "mongoId": "aabbccddee112233ff445566",
    "status": "ACTIVE",
    "verificationLevel": "VERIFIED",
    "verified": True,
    "versions": [
        {
            "current": True,
            "object": {
                "title": "Książka testowa",
                "type": "BOOK",
                "mainLanguage": "eng",
                "isbn": "978-3-16-148410-0",
                "book": {
                    "year": 2021,
                    "isbn": "978-3-16-148410-0",
                },
                "authors": {
                    "aaa111bbb222ccc333ddd443": {
                        "lastName": "Zieliński",
                        "name": "Piotr",
                    },
                },
                "keywords": {},
                "abstracts": {},
            },
        }
    ],
}


def test_pbn_provider_registered():
    providers = get_available_providers()
    assert "PBN" in providers


def test_pbn_provider_name():
    provider = PBNProvider()
    assert provider.name == "PBN"
    assert provider.identifier_label == "PBN UID lub adres URL w repozytorium PBN"


def test_get_provider_pbn():
    provider = get_provider("PBN")
    assert isinstance(provider, PBNProvider)


def test_validate_identifier_valid():
    provider = PBNProvider()
    result = provider.validate_identifier(SAMPLE_PBN_UID)
    assert result == SAMPLE_PBN_UID


def test_validate_identifier_with_spaces():
    provider = PBNProvider()
    result = provider.validate_identifier(f"  {SAMPLE_PBN_UID}  ")
    assert result == SAMPLE_PBN_UID


def test_validate_identifier_uppercase():
    provider = PBNProvider()
    uid = "5E709189878C28A04737DC6F"
    assert provider.validate_identifier(uid) == uid


def test_validate_identifier_invalid_too_short():
    provider = PBNProvider()
    assert provider.validate_identifier("abc123") is None


def test_validate_identifier_invalid_too_long():
    provider = PBNProvider()
    assert provider.validate_identifier("5e709189878c28a04737dc6fab") is None


def test_validate_identifier_invalid_non_hex():
    provider = PBNProvider()
    assert provider.validate_identifier("5e709189878c28a04737dc6z") is None


def test_validate_identifier_empty():
    provider = PBNProvider()
    assert provider.validate_identifier("") is None


def test_validate_identifier_pbn_url():
    provider = PBNProvider()
    url = f"https://pbn.nauka.gov.pl/core/#/publication/view/{SAMPLE_PBN_UID}/current"
    assert provider.validate_identifier(url) == SAMPLE_PBN_UID


def test_validate_identifier_pbn_url_trailing_slash():
    provider = PBNProvider()
    url = f"https://pbn.nauka.gov.pl/core/#/publication/view/{SAMPLE_PBN_UID}/"
    assert provider.validate_identifier(url) == SAMPLE_PBN_UID


def test_validate_identifier_pbn_url_no_trailing():
    provider = PBNProvider()
    url = f"https://pbn.nauka.gov.pl/core/#/publication/view/{SAMPLE_PBN_UID}"
    assert provider.validate_identifier(url) == SAMPLE_PBN_UID


def test_validate_identifier_pbn_url_with_spaces():
    provider = PBNProvider()
    url = (
        f"  https://pbn.nauka.gov.pl/core/#/publication/view/{SAMPLE_PBN_UID}/current  "
    )
    assert provider.validate_identifier(url) == SAMPLE_PBN_UID


def test_validate_identifier_url_without_valid_uid():
    provider = PBNProvider()
    url = "https://pbn.nauka.gov.pl/core/#/publication/view/abc/current"
    assert provider.validate_identifier(url) is None


@patch("importer_publikacji.providers.pbn._save_to_pbn_publication")
@patch("importer_publikacji.providers.pbn._get_pbn_client")
def test_fetch_success_article(mock_get_client, mock_save):
    mock_client = MagicMock()
    mock_client.get_publication_by_id.return_value = SAMPLE_PBN_ARTICLE
    mock_get_client.return_value = mock_client

    provider = PBNProvider()
    pub = provider.fetch(SAMPLE_PBN_UID)

    assert pub is not None
    assert pub.title == "Przykładowy artykuł naukowy"
    assert pub.doi == "10.1234/test.2020"
    assert pub.year == 2020
    assert pub.publication_type == "journal-article"
    assert pub.language == "pol"
    assert pub.volume == "42"
    assert pub.issue == "3"
    assert pub.pages == "100-115"
    assert pub.source_title == "Czasopismo Testowe"
    assert pub.issn == "1234-5678"
    assert pub.e_issn == "9876-5432"
    assert pub.publisher == "Wydawnictwo Testowe"
    assert pub.url == "https://example.com/pub/123"
    assert pub.license_url == "https://creativecommons.org/licenses/by/4.0/"
    assert pub.extra == {"pbn_uid": SAMPLE_PBN_UID}

    mock_client.get_publication_by_id.assert_called_once_with(SAMPLE_PBN_UID)


@patch("importer_publikacji.providers.pbn._save_to_pbn_publication")
@patch("importer_publikacji.providers.pbn._get_pbn_client")
def test_fetch_saves_to_publication(mock_get_client, mock_save):
    mock_client = MagicMock()
    mock_client.get_publication_by_id.return_value = SAMPLE_PBN_ARTICLE
    mock_get_client.return_value = mock_client

    provider = PBNProvider()
    provider.fetch(SAMPLE_PBN_UID)

    mock_save.assert_called_once_with(SAMPLE_PBN_UID, SAMPLE_PBN_ARTICLE)


@patch("importer_publikacji.providers.pbn._get_pbn_client")
def test_fetch_not_found_returns_none(mock_get_client):
    mock_client = MagicMock()
    mock_client.get_publication_by_id.side_effect = HttpException(
        404, "/api/v1/publications/id/xyz", ""
    )
    mock_get_client.return_value = mock_client

    provider = PBNProvider()
    assert provider.fetch(SAMPLE_PBN_UID) is None


@patch("importer_publikacji.providers.pbn._get_pbn_client")
def test_fetch_no_uczelnia_returns_none(mock_get_client):
    mock_get_client.side_effect = ValueError("Brak konfiguracji PBN")

    provider = PBNProvider()
    assert provider.fetch(SAMPLE_PBN_UID) is None


@patch("importer_publikacji.providers.pbn._get_pbn_client")
def test_fetch_maintenance_returns_none(mock_get_client):
    mock_client = MagicMock()
    mock_client.get_publication_by_id.side_effect = PraceSerwisoweException()
    mock_get_client.return_value = mock_client

    provider = PBNProvider()
    assert provider.fetch(SAMPLE_PBN_UID) is None


@patch("importer_publikacji.providers.pbn._get_pbn_client")
def test_fetch_access_denied_returns_none(
    mock_get_client,
):
    mock_client = MagicMock()
    mock_client.get_publication_by_id.side_effect = AccessDeniedException(
        "/api/v1/publications/id/xyz",
        "Access Denied",
    )
    mock_get_client.return_value = mock_client

    provider = PBNProvider()
    assert provider.fetch(SAMPLE_PBN_UID) is None


@patch("importer_publikacji.providers.pbn._get_pbn_client")
def test_fetch_unexpected_http_error_propagates(
    mock_get_client,
):
    mock_client = MagicMock()
    mock_client.get_publication_by_id.side_effect = HttpException(
        500,
        "/api/v1/publications/id/xyz",
        "Server Error",
    )
    mock_get_client.return_value = mock_client

    provider = PBNProvider()
    with pytest.raises(HttpException):
        provider.fetch(SAMPLE_PBN_UID)


@patch("importer_publikacji.providers.pbn._save_to_pbn_publication")
@patch("importer_publikacji.providers.pbn._get_pbn_client")
def test_fetch_book_fields(mock_get_client, mock_save):
    mock_client = MagicMock()
    mock_client.get_publication_by_id.return_value = SAMPLE_PBN_BOOK
    mock_get_client.return_value = mock_client

    provider = PBNProvider()
    pub = provider.fetch("aabbccddee112233ff445566")

    assert pub is not None
    assert pub.title == "Książka testowa"
    assert pub.publication_type == "book"
    assert pub.isbn == "978-3-16-148410-0"
    assert pub.year == 2021
    assert pub.language == "eng"


@patch("importer_publikacji.providers.pbn._save_to_pbn_publication")
@patch("importer_publikacji.providers.pbn._get_pbn_client")
def test_fetch_client_returns_none(mock_get_client, mock_save):
    """PBN client returns None (e.g. 403 handled)."""
    mock_client = MagicMock()
    mock_client.get_publication_by_id.return_value = None
    mock_get_client.return_value = mock_client

    provider = PBNProvider()
    assert provider.fetch(SAMPLE_PBN_UID) is None
    mock_save.assert_not_called()


def test_extract_authors_dict_format():
    """PBN get_publication_by_id returns authors as dict."""
    obj = {
        "authors": {
            "aaa111bbb222ccc333ddd441": {
                "lastName": "Kowalski",
                "name": "Jan",
            },
            "aaa111bbb222ccc333ddd442": {
                "lastName": "Nowak",
                "name": "Anna",
            },
        }
    }
    authors = _extract_authors(obj)
    assert len(authors) == 2
    assert authors[0] == {
        "family": "Kowalski",
        "given": "Jan",
        "orcid": "",
    }
    assert authors[1] == {
        "family": "Nowak",
        "given": "Anna",
        "orcid": "",
    }


def test_extract_authors_list_format():
    """Institution API returns authors as list of dicts."""
    obj = {
        "authors": [
            {"firstName": "Jan", "lastName": "Kowalski"},
            {"firstName": "Anna", "lastName": "Nowak"},
        ]
    }
    authors = _extract_authors(obj)
    assert len(authors) == 2
    assert authors[0] == {
        "family": "Kowalski",
        "given": "Jan",
        "orcid": "",
    }


def test_extract_authors_empty():
    assert _extract_authors({}) == []
    assert _extract_authors({"authors": {}}) == []
    assert _extract_authors({"authors": []}) == []


def test_extract_keywords():
    obj = {
        "keywords": {
            "pl": ["nauka", "testowanie"],
            "en": ["science"],
        }
    }
    kw = _extract_keywords(obj)
    assert "nauka" in kw
    assert "testowanie" in kw
    assert "science" in kw
    assert len(kw) == 3


def test_extract_keywords_empty():
    assert _extract_keywords({}) == []
    assert _extract_keywords({"keywords": {}}) == []
    assert _extract_keywords({"keywords": None}) == []


def test_extract_abstract():
    obj = {
        "abstracts": {
            "pl": "Abstrakt po polsku.",
            "en": "English abstract.",
        }
    }
    abstract = _extract_abstract(obj)
    assert abstract is not None
    assert abstract in [
        "Abstrakt po polsku.",
        "English abstract.",
    ]


def test_extract_abstract_empty():
    assert _extract_abstract({}) is None
    assert _extract_abstract({"abstracts": {}}) is None
    assert _extract_abstract({"abstracts": None}) is None


def test_extract_year_direct():
    assert _extract_year({"year": 2020}) == 2020


def test_extract_year_from_book():
    assert _extract_year({"book": {"year": 2021}}) == 2021


def test_extract_year_none():
    assert _extract_year({}) is None


def test_extract_isbn_direct():
    assert _extract_isbn({"isbn": "978-3-16-148410-0"}) == "978-3-16-148410-0"


def test_extract_isbn_from_book():
    assert _extract_isbn({"book": {"isbn": "978-3-16-148410-0"}}) == "978-3-16-148410-0"


def test_extract_isbn_none():
    assert _extract_isbn({}) is None


def test_extract_license_url():
    obj = {"openAccess": {"license": "CC_BY"}}
    assert _extract_license_url(obj) == "https://creativecommons.org/licenses/by/4.0/"


def test_extract_license_url_unknown():
    obj = {"openAccess": {"license": "UNKNOWN"}}
    assert _extract_license_url(obj) is None


def test_extract_license_url_no_open_access():
    assert _extract_license_url({}) is None


def test_type_mapping():
    assert PBN_TYPE_MAP["ARTICLE"] == "journal-article"
    assert PBN_TYPE_MAP["BOOK"] == "book"
    assert PBN_TYPE_MAP["EDITED_BOOK"] == "edited-book"
    assert PBN_TYPE_MAP["CHAPTER"] == "book-chapter"


def test_get_current_version_object():
    data = {
        "versions": [
            {
                "current": False,
                "object": {"title": "stara"},
            },
            {
                "current": True,
                "object": {"title": "nowa"},
            },
        ]
    }
    obj = _get_current_version_object(data)
    assert obj["title"] == "nowa"


def test_get_current_version_object_no_versions():
    assert _get_current_version_object({}) is None
    assert _get_current_version_object({"versions": []}) is None
