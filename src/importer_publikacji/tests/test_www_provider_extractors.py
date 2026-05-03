"""Tests for HTML metadata extractor helpers in ``providers.www``.

Covers ``_extract_citation_meta``, ``_extract_dublin_core``,
``_extract_schema_jsonld`` and ``_extract_opengraph``.
"""

from importer_publikacji.providers.www import (
    _extract_citation_meta,
    _extract_dublin_core,
    _extract_opengraph,
    _extract_schema_jsonld,
)

from ._www_provider_samples import (
    SAMPLE_HTML_CITATION,
    SAMPLE_HTML_DC,
    SAMPLE_HTML_OG,
    SAMPLE_HTML_SCHEMA_JSONLD,
    _make_soup,
)

# --- citation_* extraction ---


def test_extract_citation_meta_full():
    soup = _make_soup(SAMPLE_HTML_CITATION)
    result = _extract_citation_meta(soup)

    assert result["title"] == ("Wpływ temperatury na właściwości materiałów")
    assert len(result["authors"]) == 2
    assert result["authors"][0] == {
        "family": "Kowalski",
        "given": "Jan",
    }
    assert result["authors"][1] == {
        "family": "Nowak",
        "given": "Anna Maria",
    }
    assert result["doi"] == "10.1234/test.2024"
    assert result["source_title"] == "Journal of Materials Science"
    assert result["source_abbreviation"] == "J. Mat. Sci."
    assert result["issn"] == "1234-5678"
    assert result["volume"] == "42"
    assert result["issue"] == "3"
    assert result["pages"] == "100-115"
    assert result["year"] == 2024
    assert result["publisher"] == "Academic Press"
    assert result["language"] == "pl"
    assert result["keywords"] == [
        "materiały",
        "temperatura",
    ]
    assert result["isbn"] == "978-3-16-148410-0"


def test_extract_citation_meta_empty():
    soup = _make_soup("<html><head></head></html>")
    result = _extract_citation_meta(soup)
    assert result == {}


def test_extract_citation_firstpage_only():
    html = """
    <html><head>
    <meta name="citation_title" content="Test">
    <meta name="citation_firstpage" content="50">
    </head></html>
    """
    soup = _make_soup(html)
    result = _extract_citation_meta(soup)
    assert result["pages"] == "50"


def test_extract_citation_doi_url_cleaned():
    html = """
    <html><head>
    <meta name="citation_title" content="Test">
    <meta name="citation_doi"
      content="https://doi.org/10.5555/x">
    </head></html>
    """
    soup = _make_soup(html)
    result = _extract_citation_meta(soup)
    assert result["doi"] == "10.5555/x"


def test_extract_citation_publication_date():
    html = """
    <html><head>
    <meta name="citation_title" content="Test">
    <meta name="citation_publication_date"
      content="2025/03/01">
    </head></html>
    """
    soup = _make_soup(html)
    result = _extract_citation_meta(soup)
    assert result["year"] == 2025


# --- Schema.org JSON-LD extraction ---


def test_extract_schema_jsonld_full():
    soup = _make_soup(SAMPLE_HTML_SCHEMA_JSONLD)
    result = _extract_schema_jsonld(soup)

    assert result["title"] == "Schema Article Title"
    assert len(result["authors"]) == 2
    assert result["authors"][0] == {
        "family": "Smith",
        "given": "John",
    }
    assert result["authors"][1] == {
        "family": "Kowalska",
        "given": "Anna",
    }
    assert result["doi"] == "10.9999/schema.2023"
    assert result["year"] == 2023
    assert result["source_title"] == "Schema Journal"
    assert result["issn"] == "9999-0000"
    assert result["publisher"] == "Schema Publisher"
    assert result["volume"] == "10"
    assert result["issue"] == "2"
    assert result["pages"] == "50-60"


def test_extract_schema_jsonld_empty():
    soup = _make_soup("<html><head></head></html>")
    result = _extract_schema_jsonld(soup)
    assert result == {}


def test_extract_schema_jsonld_no_article():
    html = """
    <html><head>
    <script type="application/ld+json">
    {"@type": "WebPage", "name": "Not article"}
    </script>
    </head></html>
    """
    soup = _make_soup(html)
    result = _extract_schema_jsonld(soup)
    assert result == {}


# --- Dublin Core extraction ---


def test_extract_dublin_core_full():
    soup = _make_soup(SAMPLE_HTML_DC)
    result = _extract_dublin_core(soup)

    assert result["title"] == "Badania nad polimerem X"
    assert len(result["authors"]) == 2
    assert result["authors"][0] == {
        "family": "Wiśniewski",
        "given": "Tomasz",
    }
    assert result["authors"][1] == {
        "family": "Zielińska",
        "given": "Ewa",
    }
    assert result["year"] == 2023
    assert result["doi"] == "10.5555/dc.2023"
    assert result["source_title"] == "Polymer Journal"
    assert result["publisher"] == "Springer"
    assert result["language"] == "en"
    assert result["abstract"] == "Abstrakt badania nad polimerem."


def test_extract_dublin_core_empty():
    soup = _make_soup("<html><head></head></html>")
    result = _extract_dublin_core(soup)
    assert result == {}


# --- OpenGraph extraction ---


def test_extract_opengraph():
    soup = _make_soup(SAMPLE_HTML_OG)
    result = _extract_opengraph(soup)
    assert result["title"] == "OpenGraph Title"


def test_extract_opengraph_empty():
    soup = _make_soup("<html><head></head></html>")
    result = _extract_opengraph(soup)
    assert result == {}
