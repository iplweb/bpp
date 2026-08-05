from importer_publikacji.providers import (
    FetchedPublication,
    get_available_providers,
    get_provider,
    get_providers_metadata,
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


def test_crossref_choice_label_mentions_doi():
    """Etykieta opcji CrossRef ma jasno wskazywać wymóg numeru DOI
    (Freshdesk #381) — operator nie powinien tego wiedzieć z góry."""
    provider = CrossRefProvider()
    assert provider.choice_label == "CrossRef — wyszukiwanie po numerze DOI"
    assert "DOI" in provider.choice_label


def test_providers_metadata_exposes_choice_label():
    """Metadane przekazywane do formularza zawierają choice_label."""
    meta = get_providers_metadata()
    assert meta["CrossRef"]["choice_label"] == (
        "CrossRef — wyszukiwanie po numerze DOI"
    )
    # Provider bez nadpisania choice_label spada do nazwy.
    assert meta["BibTeX"]["choice_label"] == "BibTeX"


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


def test_crossref_fetch_filters_institutional_authors(monkeypatch):
    """CrossRef czasami zwraca jako 'autora' instytucję
    (z kluczem 'name' bez 'family'/'given'), np. dla DOI
    10.17306/j.afw.2021.4.23. Provider musi pominąć takie wpisy,
    żeby nie powstawali "puści" autorzy w wizardzie.
    """
    from importer_publikacji.providers import crossref as crossref_mod

    fake_data = {
        "title": ["Test"],
        "DOI": "10.17306/j.afw.2021.4.23",
        "author": [
            {
                "name": "Katedra Ekonomiki i Techniki Leśnej",
                "sequence": "first",
            },
            {
                "family": "Starosta-Grala",
                "given": "Monika",
                "sequence": "first",
            },
            {
                "family": "Ankudo-Jankowska",
                "given": "Anna",
                "sequence": "additional",
            },
        ],
    }

    class _FakeManager:
        def get_by_doi(self, doi):
            return fake_data

    monkeypatch.setattr(
        crossref_mod.CrossrefAPICache,
        "objects",
        _FakeManager(),
    )

    result = CrossRefProvider().fetch("10.17306/j.afw.2021.4.23")
    assert result is not None
    assert len(result.authors) == 2
    assert result.authors[0]["family"] == "Starosta-Grala"
    assert result.authors[1]["family"] == "Ankudo-Jankowska"


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
