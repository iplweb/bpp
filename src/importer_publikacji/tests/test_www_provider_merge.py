"""Tests for ``_merge_sources`` priority/complement behaviour."""

from importer_publikacji.providers.www import (
    _extract_citation_meta,
    _extract_dublin_core,
    _extract_opengraph,
    _merge_sources,
)

from ._www_provider_samples import SAMPLE_HTML_MIXED, _make_soup


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
