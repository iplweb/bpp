"""Sample HTML/JSON-LD fixtures for WWW provider tests.

Shared between ``test_www_provider*.py`` modules. Not a pytest module
(leading underscore + no ``test_`` prefix) — pytest won't collect it.
"""

from unittest.mock import MagicMock

from bs4 import BeautifulSoup

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


# Eksport XML "articles-xml.seam?year=YYYY" instancji Omega-PSIR (np. PPM
# UMLUB) — SEO sitemapa z listą URL-i stron szczegółowych artykułów,
# wpisana w robots.txt (`Sitemap: .../years-xml.seam` -> index per rok).
# Skrócona wersja realnej odpowiedzi (potwierdzone na żywo 2026-07-10,
# ~1467 wpisów dla roku 2026 na ppm.umlub.pl).
SAMPLE_OMEGA_ARTICLES_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://ppm.umlub.pl/info/article/UML001085ec4f064177b924ac8a993e7701/</loc>
    </url>
    <url>
        <loc>https://ppm.umlub.pl/info/article/UML0057c12f802b4ae7a8ef45ba8aaad38a/</loc>
    </url>
    <url>
        <loc>https://ppm.umlub.pl/info/article/UML00cc39550a89431597f0949c8c467ef4/</loc>
    </url>
</urlset>
"""

# Fragment strony `globalResultList.seam` (siatka wyników wyszukiwania
# Omega-PSIR/JSF-Seam) — trzy hidden-input ViewState (statefulny AJAX,
# jeden ViewState per <form> na stronie) i ZERO linków do pojedynczych
# prac w server-rendered HTML. Zweryfikowane na żywo 2026-07-10 na
# https://ppm.umlub.pl/globalResultList.seam?r=projectmain&tab=PROJECT —
# realna odpowiedź miała 69183 znaki, 5 ViewState, 0 dopasowań
# /info/article/ ani żadnego innego per-wpis linku. Ten fixture to
# minimalna reprezentatywna próbka tego kształtu (nie cała strona).
SAMPLE_HTML_PPM_GLOBAL_RESULT_LIST = """
<html><head><title>Wyniki wyszukiwania</title></head>
<body>
<form id="tabsForm">
<input type="hidden" name="javax.faces.ViewState"
  id="j_id__v_0:javax.faces.ViewState:1" value="opaque-viewstate-token" />
<div class="tabs">
  <a href="/globalResultList.seam?r=publication&amp;tab=PUBLICATION">
    Publikacje (1467)</a>
  <a href="/globalResultList.seam?r=projectmain&amp;tab=PROJECT">
    Projekty (42)</a>
</div>
<div id="resultGrid" data-widget="primefaces-datatable-ajax"></div>
</form>
</body></html>
"""


def _make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _mock_response(text="", status_code=200, json_data=None):
    resp = MagicMock()
    resp.text = text
    resp.content = text.encode("utf-8") if text else b""
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    if json_data is not None:
        resp.json.return_value = json_data
    if status_code >= 400:
        resp.raise_for_status.side_effect = __import__(
            "requests"
        ).exceptions.HTTPError()
    return resp
