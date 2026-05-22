"""Tests for ``DSpaceProvider`` registration, URL parsing and validation.

The original 917-line module was split into several
``test_dspace_provider_*`` files for readability. Shared sample
DSpace REST responses live in ``_dspace_provider_samples`` (non-test
module — leading underscore, no ``test_`` prefix).

Sibling test modules:
- ``test_dspace_provider_parsers`` – DC value/author/year/citation/type
  helpers and ``_resolve_url`` logic
- ``test_dspace_provider_fetch``   – full ``fetch`` flow with mocked
  HTTP for both DSpace 6 and DSpace 7
"""

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

from ._dspace_provider_samples import (
    BASE_URL,
    SAMPLE_HANDLE_URL,
    SAMPLE_URL,
    SAMPLE_UUID,
)

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


def test_parse_url_entities_publication():
    """DSpace 7+ Angular UI używa /entities/<type>/<uuid>/[details]
    zamiast /items/<uuid>. Provider musi to akceptować — REST API
    endpoint to ten sam /server/api/core/items/<uuid>."""
    url = f"{BASE_URL}/entities/publication/{SAMPLE_UUID}/details"
    result = _parse_dspace7_url(url)
    assert result == (BASE_URL, SAMPLE_UUID)


def test_parse_url_entities_without_details_suffix():
    url = f"{BASE_URL}/entities/publication/{SAMPLE_UUID}"
    result = _parse_dspace7_url(url)
    assert result == (BASE_URL, SAMPLE_UUID)


def test_parse_url_entities_other_type():
    """Inne typy entities (np. /entities/person/<uuid>) też matchują —
    DSpace pozwala każdej instancji definiować własne entity types."""
    url = f"{BASE_URL}/entities/dataset/{SAMPLE_UUID}/details"
    result = _parse_dspace7_url(url)
    assert result == (BASE_URL, SAMPLE_UUID)


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
