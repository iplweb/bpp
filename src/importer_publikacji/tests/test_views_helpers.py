"""Testy jednostkowe pomocniczych funkcji modułu `importer_publikacji.views`:
`_build_abstracts_list` (normalizacja listy streszczeń z wyniku providera)
oraz `_resolve_jezyk` (mapowanie kodu CrossRef → instancja Jezyk).
"""

from dataclasses import dataclass, field

import pytest

from importer_publikacji.views import _build_abstracts_list, _resolve_jezyk


@dataclass
class _FakeResult:
    abstract: str | None = None
    extra: dict = field(default_factory=dict)


def test_build_abstracts_list_with_extra():
    """extra['abstracts'] → zwróć je."""
    result = _FakeResult(
        abstract="Meta abstract",
        extra={"abstracts": [{"text": "Body abstract", "language": "en"}]},
    )
    abstracts = _build_abstracts_list(result)
    assert len(abstracts) == 1
    assert abstracts[0]["text"] == "Body abstract"


def test_build_abstracts_list_fallback_abstract():
    """Brak extra['abstracts'] → użyj abstract."""
    result = _FakeResult(abstract="Only abstract")
    abstracts = _build_abstracts_list(result)
    assert len(abstracts) == 1
    assert abstracts[0]["text"] == "Only abstract"
    assert abstracts[0]["language"] is None


def test_build_abstracts_list_empty():
    """Brak wszystkiego → pusta lista."""
    result = _FakeResult()
    abstracts = _build_abstracts_list(result)
    assert abstracts == []


@pytest.mark.django_db
def test_resolve_jezyk_by_crossref(jezyki):
    """Rozwiąż język po skrot_crossref."""
    jezyk = _resolve_jezyk("en")
    assert jezyk is not None
    assert jezyk.skrot_crossref == "en"


@pytest.mark.django_db
def test_resolve_jezyk_none(jezyki):
    """None → None."""
    assert _resolve_jezyk(None) is None


@pytest.mark.django_db
def test_resolve_jezyk_unknown(jezyki):
    """Nieznany kod → None."""
    assert _resolve_jezyk("xx") is None
