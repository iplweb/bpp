from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup

from importer_publikacji.providers import (
    InputMode,
    get_available_providers,
    get_provider,
)
from importer_publikacji.providers.www import (
    WWWProvider,
    _clean_doi,
    _detect_omega_psir,
    _extract_body_abstracts,
    _extract_citation_meta,
    _extract_dublin_core,
    _extract_opengraph,
    _extract_schema_jsonld,
    _merge_sources,
    _parse_author_name,
    _parse_omega_jsonld,
    _parse_year,
    _validate_url,
)

# --- Sample fixtures ---

SAMPLE_HTML_CITATION = """
<html><head>
<meta name="citation_title"
  content="Wpływ temperatury na właściwości materiałów">
<meta name="citation_author" content="Kowalski, Jan">
<meta name="citation_author" content="Nowak, Anna Maria">
<meta name="citation_doi" content="10.1234/test.2024">
<meta name="citation_journal_title"
  content="Journal of Materials Science">
<meta name="citation_journal_abbrev" content="J. Mat. Sci.">
<meta name="citation_issn" content="1234-5678">
<meta name="citation_volume" content="42">
<meta name="citation_issue" content="3">
<meta name="citation_firstpage" content="100">
<meta name="citation_lastpage" content="115">
<meta name="citation_date" content="2024/05/15">
<meta name="citation_publisher" content="Academic Press">
<meta name="citation_language" content="pl">
<meta name="citation_keywords" content="materiały">
<meta name="citation_keywords" content="temperatura">
<meta name="citation_isbn" content="978-3-16-148410-0">
</head><body><h1>Artykuł</h1></body></html>
"""

SAMPLE_HTML_DC = """
<html><head>
<meta name="DC.title"
  content="Badania nad polimerem X">
<meta name="DC.creator" content="Wiśniewski, Tomasz">
<meta name="DC.creator" content="Zielińska, Ewa">
<meta name="DC.date" content="2023-01-15">
<meta name="DC.identifier"
  content="https://doi.org/10.5555/dc.2023">
<meta name="DC.source" content="Polymer Journal">
<meta name="DC.publisher" content="Springer">
<meta name="DC.language" content="en">
<meta name="DC.description"
  content="Abstrakt badania nad polimerem.">
</head><body></body></html>
"""

SAMPLE_HTML_SCHEMA_JSONLD = """
<html><head>
<script type="application/ld+json">
{
  "@type": "ScholarlyArticle",
  "headline": "Schema Article Title",
  "author": [
    {"@type": "Person", "familyName": "Smith",
     "givenName": "John"},
    {"@type": "Person", "name": "Anna Kowalska"}
  ],
  "datePublished": "2023-06-01",
  "doi": "10.9999/schema.2023",
  "isPartOf": {
    "name": "Schema Journal",
    "issn": "9999-0000"
  },
  "publisher": {"@type": "Organization",
                "name": "Schema Publisher"},
  "volumeNumber": "10",
  "issueNumber": "2",
  "pageStart": "50",
  "pageEnd": "60"
}
</script>
</head><body></body></html>
"""

SAMPLE_HTML_OG = """
<html><head>
<meta property="og:title" content="OpenGraph Title">
</head><body></body></html>
"""

SAMPLE_OMEGA_JSONLD = [
    {
        "@id": "http://example.com/article/1",
        "@type": "ScholarlyArticle",
        "name": "Omega Article Title",
        "author": [
            {"@id": "http://example.com/person/1"},
            {"@id": "http://example.com/person/2"},
        ],
        "datePublished": "2022",
        "prism:doi": "10.7777/omega.2022",
        "inLanguage": "pl",
        "isPartOf": {"@id": "http://example.com/issue/1"},
    },
    {
        "@id": "http://example.com/person/1",
        "@type": "Person",
        "familyName": "Adamski",
        "givenName": "Piotr",
    },
    {
        "@id": "http://example.com/person/2",
        "@type": "Person",
        "familyName": "Borkowska",
        "givenName": "Maria",
    },
    {
        "@id": "http://example.com/issue/1",
        "@type": "PublicationIssue",
        "issueNumber": "4",
        "volumeNumber": "15",
        "isPartOf": {"@id": "http://example.com/journal/1"},
    },
    {
        "@id": "http://example.com/journal/1",
        "@type": "Periodical",
        "name": "Omega Czasopismo",
        "issn": "1111-2222",
        "publisher": {"name": "Omega Publisher"},
    },
]

SAMPLE_HTML_OMEGA = """
<html><head>
<meta name="citation_title"
  content="Omega Article Title from HTML">
</head><body>
<div class="article-content">
  <h1>Omega Article Title from HTML</h1>
</div>
</body></html>
"""

SAMPLE_HTML_MIXED = """
<html><head>
<meta name="citation_title"
  content="Tytuł z citation">
<meta name="citation_volume" content="5">
<meta name="DC.title"
  content="Tytuł z DC (niższy priorytet)">
<meta name="DC.description"
  content="Abstrakt z DC">
<meta name="DC.language" content="pl">
<meta property="og:title"
  content="Tytuł z OG (najniższy)">
</head><body></body></html>
"""


def _make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


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


# --- URL validation ---


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


# --- _clean_doi ---


def test_clean_doi_with_url_prefix():
    assert _clean_doi("https://doi.org/10.1234/test") == "10.1234/test"


def test_clean_doi_plain():
    assert _clean_doi("10.1234/test") == "10.1234/test"


def test_clean_doi_empty():
    assert _clean_doi("") == ""
    assert _clean_doi(None) == ""


# --- _parse_year ---


def test_parse_year_simple():
    assert _parse_year("2024") == 2024


def test_parse_year_date():
    assert _parse_year("2024/05/15") == 2024


def test_parse_year_iso():
    assert _parse_year("2024-01-01T00:00:00Z") == 2024


def test_parse_year_empty():
    assert _parse_year("") is None
    assert _parse_year(None) is None


# --- _parse_author_name ---


def test_parse_author_comma_format():
    result = _parse_author_name("Kowalski, Jan")
    assert result == {
        "family": "Kowalski",
        "given": "Jan",
    }


def test_parse_author_space_format():
    result = _parse_author_name("Jan Kowalski")
    assert result == {
        "family": "Kowalski",
        "given": "Jan",
    }


def test_parse_author_single_name():
    result = _parse_author_name("Kowalski")
    assert result == {
        "family": "Kowalski",
        "given": "",
    }


def test_parse_author_empty():
    result = _parse_author_name("")
    assert result == {"family": "", "given": ""}


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


# --- Omega-PSIR detection ---


def test_detect_omega_valid():
    # PPM = 3 letters, then 32 hex chars
    hex32 = "a" * 32
    ident_str = "PPM" + hex32
    url = "https://ppm.edu.pl/info/article/" + ident_str
    result = _detect_omega_psir(url)
    assert result is not None
    base_url, ident = result
    assert base_url == "https://ppm.edu.pl"
    assert ident == ident_str


def test_detect_omega_no_match():
    assert _detect_omega_psir("https://example.com/article/123") is None


def test_detect_omega_short_prefix():
    hex32 = "b" * 32
    url = "https://repo.edu.pl/info/article/RE" + hex32
    result = _detect_omega_psir(url)
    assert result is not None


# --- Omega-PSIR JSON-LD parsing ---


def test_parse_omega_jsonld_full():
    result = _parse_omega_jsonld(SAMPLE_OMEGA_JSONLD)

    assert result["title"] == "Omega Article Title"
    assert len(result["authors"]) == 2
    assert result["authors"][0] == {
        "family": "Adamski",
        "given": "Piotr",
    }
    assert result["authors"][1] == {
        "family": "Borkowska",
        "given": "Maria",
    }
    assert result["source_title"] == "Omega Czasopismo"
    assert result["issn"] == "1111-2222"
    assert result["volume"] == "15"
    assert result["issue"] == "4"
    assert result["year"] == 2022
    assert result["doi"] == "10.7777/omega.2022"
    assert result["language"] == "pl"
    assert result["publisher"] == "Omega Publisher"


def test_parse_omega_jsonld_empty():
    assert _parse_omega_jsonld([]) == {}
    assert _parse_omega_jsonld(None) == {}


def test_parse_omega_jsonld_no_article():
    data = [
        {
            "@id": "http://x.com/1",
            "@type": "Person",
            "name": "Test",
        }
    ]
    assert _parse_omega_jsonld(data) == {}


def test_parse_omega_author_order_preserved():
    result = _parse_omega_jsonld(SAMPLE_OMEGA_JSONLD)
    assert result["authors"][0]["family"] == "Adamski"
    assert result["authors"][1]["family"] == "Borkowska"


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


# --- Merge logic ---


def test_merge_citation_priority_over_dc():
    """citation_* ma priorytet nad Dublin Core."""
    sources = [
        {"title": "Z citation", "volume": "5"},
        {"title": "Z DC", "abstract": "Abstrakt DC"},
    ]
    merged = _merge_sources(sources)
    assert merged["title"] == "Z citation"
    assert merged["volume"] == "5"
    assert merged["abstract"] == "Abstrakt DC"


def test_merge_first_nonempty_authors():
    sources = [
        {"authors": []},
        {"authors": [{"family": "Kowalski", "given": "Jan"}]},
    ]
    merged = _merge_sources(sources)
    assert len(merged["authors"]) == 1
    assert merged["authors"][0]["family"] == "Kowalski"


def test_merge_empty_sources():
    merged = _merge_sources([{}, {}, {}])
    assert merged == {}


def test_merge_complementary_fields():
    """Pola uzupełniane z różnych źródeł."""
    soup = _make_soup(SAMPLE_HTML_MIXED)
    citation = _extract_citation_meta(soup)
    dc = _extract_dublin_core(soup)
    og = _extract_opengraph(soup)

    merged = _merge_sources([citation, dc, og])
    # Tytuł z citation (najwyższy priorytet)
    assert merged["title"] == "Tytuł z citation"
    assert merged["volume"] == "5"
    # abstract z DC (citation nie ma abstract)
    assert merged["abstract"] == "Abstrakt z DC"
    assert merged["language"] == "pl"


# --- Full fetch (mocked HTTP) ---


def _mock_response(text="", status_code=200, json_data=None):
    resp = MagicMock()
    resp.text = text
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    if json_data is not None:
        resp.json.return_value = json_data
    if status_code >= 400:
        resp.raise_for_status.side_effect = __import__(
            "requests"
        ).exceptions.HTTPError()
    return resp


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


# --- validate_identifier ---


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


# --- Body abstract extraction ---


def test_extract_body_abstract_heading():
    """h3 Abstract → tekst z następnego p."""
    html = """
    <html><body>
    <h3>Abstract</h3>
    <p>This is a long enough abstract text
    for the extraction to work properly.</p>
    </body></html>
    """
    soup = _make_soup(html)
    results = _extract_body_abstracts(soup)
    assert len(results) == 1
    assert "long enough abstract" in results[0]["text"]
    assert results[0]["language"] == "en"


def test_extract_body_abstract_dt_dd():
    """dt/dd Streszczenie → tekst z dd."""
    html = """
    <html><body>
    <dl>
    <dt>Streszczenie</dt>
    <dd>To jest wystarczająco długi tekst
    streszczenia w języku polskim.</dd>
    </dl>
    </body></html>
    """
    soup = _make_soup(html)
    results = _extract_body_abstracts(soup)
    assert len(results) == 1
    assert "wystarczająco długi" in results[0]["text"]
    assert results[0]["language"] == "pl"


def test_extract_body_abstract_strong():
    """strong z dwukropkiem → tekst z siblinga."""
    html = """
    <html><body>
    <div>
    <strong>Streszczenie:</strong>
    <span>To jest wystarczająco długi tekst
    streszczenia po tagu strong.</span>
    </div>
    </body></html>
    """
    soup = _make_soup(html)
    results = _extract_body_abstracts(soup)
    assert len(results) == 1
    assert "wystarczająco długi" in results[0]["text"]


def test_extract_body_abstract_th_td():
    """th/td w tabeli → tekst z td."""
    html = """
    <html><body>
    <table><tr>
    <th>Streszczenie</th>
    <td>To jest wystarczająco długi tekst
    streszczenia w komórce tabeli.</td>
    </tr></table>
    </body></html>
    """
    soup = _make_soup(html)
    results = _extract_body_abstracts(soup)
    assert len(results) == 1
    assert "wystarczająco długi" in results[0]["text"]


def test_extract_body_abstract_polish_label():
    """Label 'Streszczenie' → język 'pl'."""
    html = """
    <html><body>
    <h2>Streszczenie</h2>
    <p>Tekst streszczenia po polsku który jest
    wystarczająco długi do ekstrakcji.</p>
    </body></html>
    """
    soup = _make_soup(html)
    results = _extract_body_abstracts(soup)
    assert len(results) == 1
    assert results[0]["language"] == "pl"


def test_extract_body_abstract_english_label():
    """Label 'Abstract' → język 'en'."""
    html = """
    <html><body>
    <h2>Abstract</h2>
    <p>English abstract text that is long enough
    to pass the minimum length filter.</p>
    </body></html>
    """
    soup = _make_soup(html)
    results = _extract_body_abstracts(soup)
    assert len(results) == 1
    assert results[0]["language"] == "en"


def test_extract_body_abstract_multiple():
    """Dwa streszczenia (pl + en) → dwa wyniki."""
    html = """
    <html><body>
    <h3>Streszczenie</h3>
    <p>Tekst streszczenia po polsku który jest
    wystarczająco długi do ekstrakcji.</p>
    <h3>Abstract</h3>
    <p>English abstract text that is long enough
    to pass the minimum length filter.</p>
    </body></html>
    """
    soup = _make_soup(html)
    results = _extract_body_abstracts(soup)
    assert len(results) == 2
    langs = {r["language"] for r in results}
    assert langs == {"pl", "en"}


def test_extract_body_abstract_too_short_skipped():
    """Tekst <20 znaków → pominięty."""
    html = """
    <html><body>
    <h3>Abstract</h3>
    <p>Too short.</p>
    </body></html>
    """
    soup = _make_soup(html)
    results = _extract_body_abstracts(soup)
    assert len(results) == 0


def test_extract_body_abstract_dedup():
    """Ten sam tekst pod dwoma nagłówkami → jeden."""
    long_text = "A" * 50
    html = f"""
    <html><body>
    <h3>Abstract</h3>
    <p>{long_text}</p>
    <h4>Summary</h4>
    <p>{long_text}</p>
    </body></html>
    """
    soup = _make_soup(html)
    results = _extract_body_abstracts(soup)
    assert len(results) == 1


@patch("importer_publikacji.providers.www.requests.get")
def test_fetch_body_abstract_fills_extra(mock_get):
    """Integracja: body abstracts trafiają do extra."""
    html = """
    <html><head>
    <meta name="citation_title" content="Test Title">
    </head><body>
    <h3>Abstract</h3>
    <p>This is a long enough abstract text
    for the extraction to work properly.</p>
    </body></html>
    """
    mock_get.return_value = _mock_response(text=html)

    p = WWWProvider()
    pub = p.fetch("https://example.com/article")

    assert pub is not None
    assert "abstracts" in pub.extra
    assert len(pub.extra["abstracts"]) == 1
    assert pub.extra["abstracts"][0]["language"] == "en"
    # Brak abstractu z meta → body abstract jako fallback
    assert "long enough abstract" in pub.abstract
