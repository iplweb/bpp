"""Integration-style tests for ``WWWProvider.fetch`` with mocked HTTP."""

from unittest.mock import patch

from importer_publikacji.providers.www import WWWProvider

from ._www_provider_samples import (
    SAMPLE_HTML_CITATION,
    SAMPLE_HTML_DC,
    SAMPLE_HTML_MIXED,
    SAMPLE_HTML_OG,
    SAMPLE_HTML_OMEGA,
    SAMPLE_HTML_SCHEMA_JSONLD,
    SAMPLE_OMEGA_JSONLD,
    _mock_response,
)


@patch("importer_publikacji.providers.www.requests.get")
def test_fetch_citation_page(mock_get):
    mock_get.return_value = _mock_response(text=SAMPLE_HTML_CITATION)

    p = WWWProvider()
    pub = p.fetch("https://example.com/article/1")

    assert pub is not None
    assert pub.title == ("Wpływ temperatury na właściwości materiałów")
    assert pub.doi == "10.1234/test.2024"
    assert pub.year == 2024
    assert len(pub.authors) == 2
    assert pub.authors[0]["family"] == "Kowalski"
    assert pub.authors[1]["family"] == "Nowak"
    assert pub.source_title == "Journal of Materials Science"
    assert pub.issn == "1234-5678"
    assert pub.volume == "42"
    assert pub.issue == "3"
    assert pub.pages == "100-115"
    assert pub.publisher == "Academic Press"
    assert pub.language == "pl"
    assert pub.keywords == [
        "materiały",
        "temperatura",
    ]
    assert pub.isbn == "978-3-16-148410-0"
    assert pub.url == "https://example.com/article/1"
    assert pub.extra["original_url"] == "https://example.com/article/1"
    assert "citation_meta" in pub.raw_data["sources_used"]


@patch("importer_publikacji.providers.www.requests.get")
def test_fetch_omega_psir_url(mock_get):
    """Omega-PSIR URL → JSON-LD + HTML dane połączone."""
    hex32 = "a" * 32
    omega_url = "https://ppm.edu.pl/info/article/PPM" + hex32

    def side_effect(url, **kwargs):
        if "/seam/resource/rest/" in url:
            return _mock_response(json_data=SAMPLE_OMEGA_JSONLD)
        return _mock_response(text=SAMPLE_HTML_OMEGA)

    mock_get.side_effect = side_effect

    p = WWWProvider()
    pub = p.fetch(omega_url)

    assert pub is not None
    # citation_meta has priority over omega jsonld
    assert pub.title == "Omega Article Title from HTML"
    # Authors from omega jsonld (citation has none)
    assert len(pub.authors) == 2
    assert pub.authors[0]["family"] == "Adamski"
    assert pub.authors[1]["family"] == "Borkowska"
    assert "omega_psir" in pub.raw_data["sources_used"]
    assert "citation_meta" in pub.raw_data["sources_used"]


@patch("importer_publikacji.providers.www.requests.get")
def test_fetch_http_error(mock_get):
    mock_get.return_value = _mock_response(status_code=404)

    p = WWWProvider()
    pub = p.fetch("https://example.com/article/1")
    assert pub is None


@patch("importer_publikacji.providers.www.requests.get")
def test_fetch_connection_error(mock_get):
    mock_get.side_effect = __import__("requests").exceptions.ConnectionError()

    p = WWWProvider()
    pub = p.fetch("https://example.com/article/1")
    assert pub is None


@patch("importer_publikacji.providers.www.requests.get")
def test_fetch_timeout(mock_get):
    mock_get.side_effect = __import__("requests").exceptions.Timeout()

    p = WWWProvider()
    pub = p.fetch("https://example.com/article/1")
    assert pub is None


@patch("importer_publikacji.providers.www.requests.get")
def test_fetch_no_title(mock_get):
    html = "<html><head></head><body>No data</body></html>"
    mock_get.return_value = _mock_response(text=html)

    p = WWWProvider()
    pub = p.fetch("https://example.com/empty")
    assert pub is None


@patch("importer_publikacji.providers.www.requests.get")
def test_fetch_minimal_title_only(mock_get):
    html = """
    <html><head>
    <meta name="citation_title" content="Tylko tytuł">
    </head><body></body></html>
    """
    mock_get.return_value = _mock_response(text=html)

    p = WWWProvider()
    pub = p.fetch("https://example.com/minimal")

    assert pub is not None
    assert pub.title == "Tylko tytuł"
    assert pub.authors == []
    assert pub.year is None
    assert pub.doi is None
    assert pub.volume is None
    assert pub.keywords == []


def test_fetch_invalid_url():
    p = WWWProvider()
    pub = p.fetch("")
    assert pub is None


def test_fetch_empty_string():
    p = WWWProvider()
    pub = p.fetch("   ")
    assert pub is None


@patch("importer_publikacji.providers.www.requests.get")
def test_fetch_dc_only(mock_get):
    """Strona z tylko Dublin Core meta tagami."""
    mock_get.return_value = _mock_response(text=SAMPLE_HTML_DC)

    p = WWWProvider()
    pub = p.fetch("https://example.com/dc-article")

    assert pub is not None
    assert pub.title == "Badania nad polimerem X"
    assert len(pub.authors) == 2
    assert pub.year == 2023
    assert pub.doi == "10.5555/dc.2023"
    assert pub.source_title == "Polymer Journal"
    assert pub.publisher == "Springer"
    assert pub.language == "en"
    assert pub.abstract == "Abstrakt badania nad polimerem."


@patch("importer_publikacji.providers.www.requests.get")
def test_fetch_og_only(mock_get):
    """Strona z tylko OpenGraph — minimalny fallback."""
    mock_get.return_value = _mock_response(text=SAMPLE_HTML_OG)

    p = WWWProvider()
    pub = p.fetch("https://example.com/og-page")

    assert pub is not None
    assert pub.title == "OpenGraph Title"
    assert pub.authors == []
    assert pub.doi is None


@patch("importer_publikacji.providers.www.requests.get")
def test_fetch_schema_jsonld_only(mock_get):
    """Strona z Schema.org JSON-LD."""
    mock_get.return_value = _mock_response(text=SAMPLE_HTML_SCHEMA_JSONLD)

    p = WWWProvider()
    pub = p.fetch("https://example.com/schema")

    assert pub is not None
    assert pub.title == "Schema Article Title"
    assert len(pub.authors) == 2
    assert pub.doi == "10.9999/schema.2023"
    assert pub.year == 2023
    assert pub.source_title == "Schema Journal"
    assert pub.issn == "9999-0000"
    assert pub.publisher == "Schema Publisher"
    assert pub.volume == "10"
    assert pub.issue == "2"
    assert pub.pages == "50-60"


@patch("importer_publikacji.providers.www.requests.get")
def test_fetch_mixed_sources(mock_get):
    """Pola z wielu źródeł łączone razem."""
    mock_get.return_value = _mock_response(text=SAMPLE_HTML_MIXED)

    p = WWWProvider()
    pub = p.fetch("https://example.com/mixed")

    assert pub is not None
    assert pub.title == "Tytuł z citation"
    assert pub.volume == "5"
    assert pub.abstract == "Abstrakt z DC"
    assert pub.language == "pl"
