"""Regresja Freshdesk #344.

Wpis BibTeX z autorami rozdzielonymi ``and`` na osobnych liniach (typowy
format z czasopism / Zotero) powodowal 500 w imporcie: ``_parse_authors``
dzielil po literalnym ``" and "`` (ze spacja), wiec separator ``" and\\n"``
nie pasowal i WSZYSCY autorzy ladowali do jednego ImportedAuthor. Wynikowy
string (>700 znakow) przekraczal varchar(255)/varchar(512) ->
StringDataRightTruncation -> DataError przy ImportedAuthor.objects.create.

Dokladnie ten wpis z ticketu (zachowane znaki nowej linii!).
"""

import pytest

from importer_publikacji.models import ImportSession
from importer_publikacji.providers.bibtex import (
    BibTeXProvider,
    _clean_pages,
    _parse_authors,
)
from importer_publikacji.tasks import fetch_session_task

# UWAGA: znaki nowej linii w polu author sa istotne dla regresji.
BIBTEX_344 = """@article{Wierda2026,
author = {Wierda, William G. and
Brown, Jennifer R. and
Ghia, Paolo and
Roeker, Lindsey E. and
Lech-Maranda, Ewa and
Jurczak, Wojciech and
Woyach, Jennifer A.},
title = {Pirtobrutinib in post-{cBTKi} chronic lymphocytic leukemia/small lymphocytic lymphoma ({CLL}/{SLL}): {Phase} 1/2 {BRUIN} study with >5 years follow-up},
journal = {British Journal of Haematology},
year = {2026},
volume = {208},
number = {1},
pages = {S180—S180},
note = {Supplement 1, Meeting Abstract OR04.02}
}"""


def test_parse_authors_splits_on_newline_separated_and():
    """``and`` na koncu linii to wciaz separator autorow."""
    raw = "Wierda, William G. and\nBrown, Jennifer R. and\nGhia, Paolo"
    authors = _parse_authors(raw)
    assert len(authors) == 3
    assert authors[0] == {"family": "Wierda", "given": "William G."}
    assert authors[1] == {"family": "Brown", "given": "Jennifer R."}
    # Zadne pole nie moze przekroczyc limitu kolumny (255).
    for a in authors:
        assert len(a["family"]) <= 255
        assert len(a["given"]) <= 255


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("S180—S180", "S180-S180"),  # em-dash (z ticketu)
        ("100–110", "100-110"),  # en-dash
        ("100--110", "100-110"),  # LaTeX double
        ("100---110", "100-110"),  # LaTeX triple
        ("S1−S5", "S1-S5"),  # minus unicode
        ("12-15", "12-15"),  # juz ASCII
        ("", ""),
    ],
)
def test_clean_pages_normalizes_dashes(raw, expected):
    assert _clean_pages(raw) == expected


def test_fetch_parses_all_authors_from_multiline_bibtex():
    result = BibTeXProvider().fetch(BIBTEX_344)
    assert result is not None
    assert len(result.authors) == 7
    assert result.authors[0]["family"] == "Wierda"
    assert result.authors[-1]["family"] == "Woyach"
    # em-dash w stronach znormalizowany do ASCII '-'
    assert result.pages == "S180-S180"


@pytest.mark.django_db
def test_freshdesk_344_full_fetch_pipeline_no_crash(importer_user, settings):
    """Caly pipeline pobierania nie moze wywalic sie na dlugim polu autora."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True

    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="BibTeX",
        identifier=BIBTEX_344,
        status=ImportSession.Status.FETCHING,
        raw_data={},
        normalized_data={},
    )

    fetch_session_task.apply(args=[session.pk, importer_user.pk]).get()

    session.refresh_from_db()
    assert session.status == ImportSession.Status.FETCHED, (
        f"{session.status}: {session.last_error_message}\n"
        f"{session.last_error_traceback}"
    )
    assert session.authors.count() == 7
