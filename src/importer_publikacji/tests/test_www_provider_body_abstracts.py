"""Tests for body-level abstract extraction (``_extract_body_abstracts``)."""

from unittest.mock import patch

from importer_publikacji.providers.www import (
    WWWProvider,
    _extract_body_abstracts,
)

from ._www_provider_samples import _make_soup, _mock_response


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
