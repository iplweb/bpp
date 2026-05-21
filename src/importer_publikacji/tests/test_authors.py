from unittest.mock import patch

import pytest
from model_bakery import baker

from importer_publikacji.models import ImportSession
from importer_publikacji.views.authors import (
    _auto_match_authors,
    _auto_match_single_author,
)


@pytest.mark.django_db
def test_auto_match_single_author_creates_imported_author():
    session = baker.make(ImportSession)
    author_data = {"family": "Kowalski", "given": "Jan", "orcid": ""}

    imported = _auto_match_single_author(session, author_data, order=0, year=2024)

    assert imported.pk is not None
    assert imported.session_id == session.pk
    assert imported.family_name == "Kowalski"
    assert imported.given_name == "Jan"
    assert imported.order == 0


@pytest.mark.django_db
def test_auto_match_authors_calls_single_per_author():
    session = baker.make(ImportSession)
    authors_data = [
        {"family": "Kowalski", "given": "Jan", "orcid": ""},
        {"family": "Nowak", "given": "Anna", "orcid": ""},
    ]

    with patch(
        "importer_publikacji.views.authors._auto_match_single_author"
    ) as mock_single:
        _auto_match_authors(session, authors_data, year=2024)

    assert mock_single.call_count == 2
    assert mock_single.call_args_list[0].args[2] == 0
    assert mock_single.call_args_list[1].args[2] == 1
