"""Tests for low-level parser helpers in ``providers.www``.

Covers ``_clean_doi``, ``_parse_year``, ``_parse_author_name``,
``_detect_omega_psir`` and ``_parse_omega_jsonld``.
"""

from importer_publikacji.providers.www import (
    _clean_doi,
    _detect_omega_psir,
    _parse_author_name,
    _parse_omega_jsonld,
    _parse_year,
)

from ._www_provider_samples import SAMPLE_OMEGA_JSONLD

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
