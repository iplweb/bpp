from unittest.mock import MagicMock, patch

import pytest
from model_bakery import baker

from importer_publikacji.models import ImportSession
from importer_publikacji.progress import ProviderReturnedNothing
from importer_publikacji.tasks import fetch_session_task


@pytest.fixture
def fetch_session(db, django_user_model):
    user = baker.make(django_user_model)
    return baker.make(
        ImportSession,
        created_by=user,
        provider_name="crossref",
        identifier="10.1234/test",
        status=ImportSession.Status.FETCHING,
    )


@pytest.mark.django_db
def test_fetch_session_task_success_sets_status_fetched(fetch_session):
    fake_result = MagicMock(
        raw_data={"k": "v"},
        title="Test",
        doi="10.1234/test",
        year=2024,
        authors=[],
        source_title="",
        source_abbreviation="",
        issn="",
        e_issn="",
        isbn="",
        e_isbn="",
        publisher="",
        publication_type="article",
        language="en",
        abstract="",
        volume="",
        issue="",
        pages="",
        url="",
        license_url="",
        keywords=[],
        extra={},
    )

    with patch("importer_publikacji.tasks.get_provider") as mock_get_provider:
        provider = MagicMock()
        provider.fetch.return_value = fake_result
        mock_get_provider.return_value = provider

        fetch_session_task.apply(
            args=[fetch_session.pk, fetch_session.created_by_id]
        ).get()

    fetch_session.refresh_from_db()
    assert fetch_session.status == ImportSession.Status.FETCHED
    assert fetch_session.celery_task_id == ""
    assert fetch_session.last_error_message == ""


@pytest.mark.django_db
def test_fetch_session_task_provider_returns_none_marks_failed(fetch_session):
    with patch("importer_publikacji.tasks.get_provider") as mock_get_provider:
        provider = MagicMock()
        provider.fetch.return_value = None
        mock_get_provider.return_value = provider

        with pytest.raises(ProviderReturnedNothing):
            fetch_session_task.apply(
                args=[fetch_session.pk, fetch_session.created_by_id]
            ).get()

    fetch_session.refresh_from_db()
    assert fetch_session.status == ImportSession.Status.IMPORT_FAILED
    assert fetch_session.last_failed_stage == "fetch"
    assert "dostawcy" in fetch_session.last_error_message.lower()
    assert fetch_session.last_error_traceback != ""


@pytest.mark.django_db
def test_fetch_session_task_provider_raises_marks_failed(fetch_session):
    with patch("importer_publikacji.tasks.get_provider") as mock_get_provider:
        provider = MagicMock()
        provider.fetch.side_effect = RuntimeError("boom")
        mock_get_provider.return_value = provider

        with pytest.raises(RuntimeError, match="boom"):
            fetch_session_task.apply(
                args=[fetch_session.pk, fetch_session.created_by_id]
            ).get()

    fetch_session.refresh_from_db()
    assert fetch_session.status == ImportSession.Status.IMPORT_FAILED
    assert fetch_session.last_failed_stage == "fetch"
    assert "administrator" in fetch_session.last_error_message.lower()
    assert "boom" in fetch_session.last_error_traceback


@pytest.mark.django_db
def test_fetch_session_task_processes_authors(fetch_session):
    fake_result = MagicMock(
        raw_data={"k": "v"},
        title="Test",
        doi="10.1234/test",
        year=2024,
        authors=[
            {"family": "Kowalski", "given": "Jan", "orcid": ""},
            {"family": "Nowak", "given": "Anna", "orcid": ""},
        ],
        source_title="",
        source_abbreviation="",
        issn="",
        e_issn="",
        isbn="",
        e_isbn="",
        publisher="",
        publication_type="",
        language="",
        abstract="",
        volume="",
        issue="",
        pages="",
        url="",
        license_url="",
        keywords=[],
        extra={},
    )

    with patch("importer_publikacji.tasks.get_provider") as mock_get_provider:
        provider = MagicMock()
        provider.fetch.return_value = fake_result
        mock_get_provider.return_value = provider

        fetch_session_task.apply(
            args=[fetch_session.pk, fetch_session.created_by_id]
        ).get()

    fetch_session.refresh_from_db()
    assert fetch_session.authors.count() == 2
    assert fetch_session.status == ImportSession.Status.FETCHED
