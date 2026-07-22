from unittest.mock import MagicMock, patch

import pytest
from model_bakery import baker

from importer_publikacji.models import ImportSession
from importer_publikacji.tasks import create_publication_task, fetch_session_task


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
        patent_number=None,
        patent_grant_number=None,
        filing_date=None,
        grant_date=None,
        patent_type=None,
        patent_holder=None,
        jurisdiction=None,
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
    """Provider zwracający None to oczekiwany failure (publikacja nie
    znaleziona). Task NIE rzuca wyjątku — żeby Celery nie logował
    ERROR-a ani @task_failure.connect nie zgłaszał do Rollbara.
    Status sesji wystarczy do pokazania user-owi komunikatu.
    """
    with patch("importer_publikacji.tasks.get_provider") as mock_get_provider:
        provider = MagicMock()
        provider.fetch.return_value = None
        mock_get_provider.return_value = provider

        # Bez pytest.raises: task kończy się sukcesem z punktu widzenia
        # Celery, ale session.status == IMPORT_FAILED.
        fetch_session_task.apply(
            args=[fetch_session.pk, fetch_session.created_by_id]
        ).get()

    fetch_session.refresh_from_db()
    assert fetch_session.status == ImportSession.Status.IMPORT_FAILED
    assert fetch_session.last_failed_stage == "fetch"
    assert "dostawcy" in fetch_session.last_error_message.lower()
    assert fetch_session.celery_task_id == ""
    # Brak traceback dla expected failure — nie szliśmy przez except.
    assert fetch_session.last_error_traceback == ""


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
        patent_number=None,
        patent_grant_number=None,
        filing_date=None,
        grant_date=None,
        patent_type=None,
        patent_holder=None,
        jurisdiction=None,
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


@pytest.mark.django_db
def test_fetch_session_task_stores_patent_fields(fetch_session):
    """Pola patentowe z FetchedPublication (real dataclass, nie MagicMock)
    musza przetrwac do session.normalized_data — inaczej _create_patent nie
    ma z czego uzupelnic numer_zgloszenia/data_zgloszenia/etc w prawdziwym
    (nie testowym) fetchu."""
    from importer_publikacji.providers import FetchedPublication

    fake_result = FetchedPublication(
        raw_data={"bibtex_type": "patent"},
        title="A New Widget",
        year=2024,
        authors=[],
        publication_type="patent",
        patent_number="PL123456",
        patent_holder="ACME Corp",
        jurisdiction="Poland",
        patent_type="patent",
        filing_date="2024-03-15",
    )

    with patch("importer_publikacji.tasks.get_provider") as mock_get_provider:
        provider = MagicMock()
        provider.fetch.return_value = fake_result
        mock_get_provider.return_value = provider

        fetch_session_task.apply(
            args=[fetch_session.pk, fetch_session.created_by_id]
        ).get()

    fetch_session.refresh_from_db()
    nd = fetch_session.normalized_data
    assert nd["patent_number"] == "PL123456"
    assert nd["patent_holder"] == "ACME Corp"
    assert nd["jurisdiction"] == "Poland"
    assert nd["patent_type"] == "patent"
    assert nd["filing_date"] == "2024-03-15"
    assert nd["patent_grant_number"] is None
    assert nd["grant_date"] is None


@pytest.fixture
def review_session(db, django_user_model):
    user = baker.make(django_user_model)
    return baker.make(
        ImportSession,
        created_by=user,
        provider_name="crossref",
        identifier="10.1234/test",
        status=ImportSession.Status.CREATING,
        normalized_data={"title": "Test", "year": 2024},
    )


@pytest.mark.django_db
def test_create_publication_task_success_sets_completed(review_session):
    from django.contrib.contenttypes.models import ContentType

    fake_record = MagicMock(pk=42)
    any_ct = ContentType.objects.first()
    with (
        patch("importer_publikacji.tasks._create_publication") as mock_create,
        patch(
            "importer_publikacji.tasks.ContentType.objects.get_for_model",
            return_value=any_ct,
        ),
    ):
        mock_create.return_value = fake_record

        create_publication_task.apply(
            args=[review_session.pk, review_session.created_by_id, False]
        ).get()

    review_session.refresh_from_db()
    assert review_session.status == ImportSession.Status.COMPLETED
    assert review_session.celery_task_id == ""


@pytest.mark.django_db
def test_create_publication_task_failure_marks_import_failed(review_session):
    with patch("importer_publikacji.tasks._create_publication") as mock_create:
        mock_create.side_effect = RuntimeError("create exploded")

        with pytest.raises(RuntimeError, match="create exploded"):
            create_publication_task.apply(
                args=[review_session.pk, review_session.created_by_id, False]
            ).get()

    review_session.refresh_from_db()
    assert review_session.status == ImportSession.Status.IMPORT_FAILED
    assert review_session.last_failed_stage == "create"
    assert "administrator" in review_session.last_error_message.lower()


@pytest.mark.django_db
def test_create_publication_task_with_pbn_calls_pbn_export(review_session):
    from django.contrib.contenttypes.models import ContentType

    fake_record = MagicMock(pk=42)
    any_ct = ContentType.objects.first()
    with (
        patch("importer_publikacji.tasks._create_publication") as mock_create,
        patch(
            "bpp.admin.helpers.pbn_api.gui.sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui"
        ) as mock_pbn,
        patch(
            "importer_publikacji.tasks.ContentType.objects.get_for_model",
            return_value=any_ct,
        ),
    ):
        mock_create.return_value = fake_record

        create_publication_task.apply(
            args=[review_session.pk, review_session.created_by_id, True]
        ).get()

    mock_pbn.assert_called_once()
    assert mock_pbn.call_args.args[1] == fake_record
