"""Tests for ``WWWProvider`` registration, identity and URL validation.

The original 993-line module was split into several ``test_www_provider_*``
files for readability. Shared HTML/JSON-LD fixtures live in
``_www_provider_samples`` (non-test module).

Sibling test modules:
- ``test_www_provider_parsers``        – low-level parser helpers
- ``test_www_provider_extractors``     – per-format meta extractors
- ``test_www_provider_merge``          – ``_merge_sources`` priority logic
- ``test_www_provider_fetch``          – full ``fetch`` flow with mocked HTTP
- ``test_www_provider_body_abstracts`` – body-level abstract extraction
"""

from importer_publikacji.providers import (
    InputMode,
    get_available_providers,
    get_provider,
)
from importer_publikacji.providers.www import (
    WWWProvider,
    _validate_url,
)

# --- Registration ---


def test_www_provider_registered():
    providers = get_available_providers()
    assert "Pozostałe strony WWW" in providers


def test_www_provider_name():
    p = WWWProvider()
    assert p.name == "Pozostałe strony WWW"
    assert p.identifier_label == "Adres URL strony z publikacją"


def test_www_provider_input_mode():
    p = WWWProvider()
    assert p.input_mode == InputMode.IDENTIFIER


def test_get_provider_www():
    p = get_provider("Pozostałe strony WWW")
    assert isinstance(p, WWWProvider)


# --- URL validation (_validate_url) ---


def test_validate_url_valid():
    assert (
        _validate_url("https://example.com/article/1")
        == "https://example.com/article/1"
    )


def test_validate_url_no_scheme():
    result = _validate_url("example.com/article/1")
    assert result == "https://example.com/article/1"


def test_validate_url_empty():
    assert _validate_url("") is None
    assert _validate_url("   ") is None


def test_validate_url_invalid():
    assert _validate_url("ftp://example.com") is None


def test_validate_url_http():
    result = _validate_url("http://example.com/article")
    assert result == "http://example.com/article"


# --- validate_identifier (provider-level) ---


def test_validate_identifier_valid():
    p = WWWProvider()
    result = p.validate_identifier("https://example.com/article")
    assert result == "https://example.com/article"


def test_validate_identifier_no_scheme():
    p = WWWProvider()
    result = p.validate_identifier("example.com/article")
    assert result == "https://example.com/article"


def test_validate_identifier_empty():
    p = WWWProvider()
    assert p.validate_identifier("") is None
    assert p.validate_identifier("   ") is None
