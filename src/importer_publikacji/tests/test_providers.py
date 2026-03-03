from importer_publikacji.providers import (
    FetchedPublication,
    get_available_providers,
    get_provider,
)
from importer_publikacji.providers.crossref import (
    CrossRefProvider,
    _extract_isbn,
    _extract_issn,
    _extract_orcid,
)


def test_crossref_provider_registered():
    """CrossRef powinien być zarejestrowany."""
    providers = get_available_providers()
    assert "CrossRef" in providers


def test_crossref_provider_name():
    provider = CrossRefProvider()
    assert provider.name == "CrossRef"
    assert provider.identifier_label == "Identyfikator DOI"


def test_crossref_validate_identifier_valid():
    provider = CrossRefProvider()
    result = provider.validate_identifier("https://doi.org/10.1234/test")
    assert result == "10.1234/test"


def test_crossref_validate_identifier_invalid():
    provider = CrossRefProvider()
    result = provider.validate_identifier("")
    assert result is None


def test_crossref_validate_identifier_plain_doi():
    provider = CrossRefProvider()
    result = provider.validate_identifier("10.1234/test")
    assert result == "10.1234/test"


def test_get_provider_crossref():
    provider = get_provider("CrossRef")
    assert isinstance(provider, CrossRefProvider)


def test_extract_orcid_from_url():
    assert (
        _extract_orcid("https://orcid.org/0000-0001-2345-6789") == "0000-0001-2345-6789"
    )


def test_extract_orcid_plain():
    assert _extract_orcid("0000-0001-2345-6789") == "0000-0001-2345-6789"


def test_extract_orcid_empty():
    assert _extract_orcid("") == ""


def test_extract_issn_with_types():
    data = {
        "issn-type": [
            {"type": "print", "value": "1234-5678"},
            {"type": "electronic", "value": "9876-5432"},
        ]
    }
    issn, e_issn = _extract_issn(data)
    assert issn == "1234-5678"
    assert e_issn == "9876-5432"


def test_extract_issn_fallback_to_issn_field():
    data = {"ISSN": ["1234-5678"]}
    issn, e_issn = _extract_issn(data)
    assert issn == "1234-5678"
    assert e_issn is None


def test_extract_isbn_with_types():
    data = {
        "isbn-type": [
            {"type": "print", "value": "978-3-16-148410-0"},
            {
                "type": "electronic",
                "value": "978-3-16-148410-1",
            },
        ]
    }
    isbn, e_isbn = _extract_isbn(data)
    assert isbn == "978-3-16-148410-0"
    assert e_isbn == "978-3-16-148410-1"


def test_fetched_publication_dataclass():
    pub = FetchedPublication(
        raw_data={"test": True},
        title="Test Title",
        doi="10.1234/test",
    )
    assert pub.title == "Test Title"
    assert pub.doi == "10.1234/test"
    assert pub.authors == []
    assert pub.keywords == []
    assert pub.extra == {}
