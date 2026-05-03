"""Parser/helper tests for ``DSpaceProvider``.

Covers the low-level helpers from ``importer_publikacji.providers.
dspace_common``: DC value lookups, author parsing, year parsing,
volume/issue/pages extraction, citation-string parsing, type mapping
and ``_resolve_url`` fallbacks. See ``test_dspace_provider`` module
docstring for the full split layout.
"""

from importer_publikacji.providers.dspace_common import (
    DSPACE_TYPE_MAP,
    _extract_volume_issue_pages,
    _get_dc_value,
    _get_dc_values,
    _parse_citation_string,
    _parse_dspace_authors,
    _parse_year,
    _resolve_url,
)

from ._dspace_provider_samples import FLAT_META

# --- DC value helpers ---


def test_get_dc_value_existing():
    assert _get_dc_value(FLAT_META, "dc.title") == "Przykładowa publikacja naukowa"


def test_get_dc_value_missing():
    assert _get_dc_value(FLAT_META, "dc.nonexistent") is None


def test_get_dc_values_multiple():
    values = _get_dc_values(FLAT_META, "dc.subject")
    assert values == ["nauka", "testowanie"]


def test_get_dc_values_empty():
    assert _get_dc_values(FLAT_META, "dc.nonexistent") == []


# --- Author parsing ---


def test_parse_authors_surname_given():
    meta = [
        {
            "key": "dc.contributor.author",
            "value": "Kowalski, Jan",
        },
        {
            "key": "dc.contributor.author",
            "value": "Nowak, Anna Maria",
        },
    ]
    result = _parse_dspace_authors(meta)
    assert len(result) == 2
    assert result[0] == {
        "family": "Kowalski",
        "given": "Jan",
        "orcid": "",
    }
    assert result[1] == {
        "family": "Nowak",
        "given": "Anna Maria",
        "orcid": "",
    }


def test_parse_authors_no_comma():
    meta = [
        {
            "key": "dc.contributor.author",
            "value": "Jan Kowalski",
        }
    ]
    result = _parse_dspace_authors(meta)
    assert len(result) == 1
    assert result[0]["family"] == "Kowalski"
    assert result[0]["given"] == "Jan"


def test_parse_authors_single_name():
    meta = [
        {
            "key": "dc.contributor.author",
            "value": "Kowalski",
        }
    ]
    result = _parse_dspace_authors(meta)
    assert len(result) == 1
    assert result[0]["family"] == "Kowalski"
    assert result[0]["given"] == ""


def test_parse_authors_empty():
    assert _parse_dspace_authors([]) == []


# --- Year parsing ---


def test_parse_year_simple():
    assert _parse_year("2020") == 2020


def test_parse_year_date():
    assert _parse_year("2020-05-15") == 2020


def test_parse_year_iso():
    assert _parse_year("2020-05-15T10:30:00Z") == 2020


def test_parse_year_empty():
    assert _parse_year("") is None
    assert _parse_year(None) is None


# --- Volume/issue/pages extraction ---


def test_extract_explicit_fields():
    meta = [
        {
            "key": "dc.bibliographicCitation.volume",
            "value": "42",
        },
        {
            "key": "dc.bibliographicCitation.issue",
            "value": "3",
        },
        {
            "key": "dc.bibliographicCitation.startPage",
            "value": "100",
        },
        {
            "key": "dc.bibliographicCitation.endPage",
            "value": "115",
        },
    ]
    vol, iss, pages = _extract_volume_issue_pages(meta)
    assert vol == "42"
    assert iss == "3"
    assert pages == "100-115"


def test_extract_start_page_only():
    meta = [
        {
            "key": "dc.bibliographicCitation.startPage",
            "value": "50",
        },
    ]
    vol, iss, pages = _extract_volume_issue_pages(meta)
    assert pages == "50"


def test_extract_citation_fallback():
    meta = [
        {
            "key": "dc.identifier.citation",
            "value": ("J. Testing, Vol. 10, No. 2, pp. 50-60"),
        }
    ]
    vol, iss, pages = _extract_volume_issue_pages(meta)
    assert vol == "10"
    assert iss == "2"
    assert pages == "50-60"


def test_extract_citation_issue_format():
    meta = [
        {
            "key": "dc.identifier.citation",
            "value": "Journal, Vol. 5, Issue 8",
        }
    ]
    vol, iss, pages = _extract_volume_issue_pages(meta)
    assert vol == "5"
    assert iss == "8"
    assert pages is None


def test_extract_empty():
    vol, iss, pages = _extract_volume_issue_pages([])
    assert vol is None
    assert iss is None
    assert pages is None


# --- Citation string parsing (Polish format) ---


def test_parse_citation_polish_format():
    vol, iss, pages = _parse_citation_string("2025 vol. 33 s.195 - 205")
    assert vol == "33"
    assert pages == "195-205"


def test_parse_citation_standard_format():
    vol, iss, pages = _parse_citation_string("J. Testing, Vol. 10, No. 2, pp. 50-60")
    assert vol == "10"
    assert iss == "2"
    assert pages == "50-60"


# --- Type mapping ---


def test_type_map_article():
    assert DSPACE_TYPE_MAP["article"] == "journal-article"


def test_type_map_book():
    assert DSPACE_TYPE_MAP["book"] == "book"


def test_type_map_book_chapter():
    assert DSPACE_TYPE_MAP["book chapter"] == "book-chapter"


def test_type_map_thesis():
    assert DSPACE_TYPE_MAP["doctoral thesis"] == "dissertation"


def test_type_map_unknown():
    assert DSPACE_TYPE_MAP.get("unknown type") is None


# --- _resolve_url tests ---


def test_resolve_url_normal_http():
    """dc.identifier.uri z HTTP → użyj go."""
    meta = [
        {
            "key": "dc.identifier.uri",
            "value": "https://repo.example.com/handle/1/2",
        },
    ]
    assert _resolve_url(meta) == ("https://repo.example.com/handle/1/2")


def test_resolve_url_doi_fallback_to_dc_identifier():
    """dc.identifier.uri = DOI → użyj dc.identifier."""
    meta = [
        {
            "key": "dc.identifier.uri",
            "value": "10.1234/test.2020",
        },
        {
            "key": "dc.identifier",
            "value": "https://hdl.handle.net/123/456",
        },
    ]
    assert _resolve_url(meta) == ("https://hdl.handle.net/123/456")


def test_resolve_url_doi_no_fallback():
    """dc.identifier.uri = DOI, brak dc.identifier → DOI."""
    meta = [
        {
            "key": "dc.identifier.uri",
            "value": "10.1234/test.2020",
        },
    ]
    assert _resolve_url(meta) == "10.1234/test.2020"


def test_resolve_url_missing():
    """Brak dc.identifier.uri → None."""
    assert _resolve_url([]) is None


def test_resolve_url_dc_identifier_non_http():
    """dc.identifier.uri = DOI, dc.identifier nie-HTTP."""
    meta = [
        {
            "key": "dc.identifier.uri",
            "value": "10.1234/test",
        },
        {
            "key": "dc.identifier",
            "value": "some-local-id",
        },
    ]
    # dc.identifier nie jest HTTP,
    # więc zwraca oryginalny uri (DOI)
    assert _resolve_url(meta) == "10.1234/test"
