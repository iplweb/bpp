from unittest.mock import patch

import pytest
from django.urls import reverse
from model_bakery import baker

from importer_publikacji.models import ImportedAuthor, ImportSession


@pytest.fixture
def authed_client(client, django_user_model):
    user = baker.make(
        django_user_model,
        is_staff=True,
        is_superuser=True,
    )
    user.set_password("test")
    user.save()
    client.force_login(user)
    return client, user


@pytest.mark.django_db
def test_retry_fetch_clears_state_and_enqueues_fetch_task(authed_client):
    client, user = authed_client
    session = baker.make(
        ImportSession,
        created_by=user,
        status=ImportSession.Status.IMPORT_FAILED,
        last_failed_stage="fetch",
        last_error_message="boom",
        last_error_traceback="tb",
        raw_data={"x": 1},
        normalized_data={"title": "stara"},
    )
    baker.make(ImportedAuthor, session=session, _quantity=3)
    assert session.authors.count() == 3

    url = reverse("importer_publikacji:task-retry", kwargs={"session_id": session.pk})

    with patch("importer_publikacji.views.retry.fetch_session_task") as mock_task:
        mock_task.delay.return_value.id = "new-task-id"
        response = client.post(url)

    session.refresh_from_db()
    assert response.status_code == 302
    assert "task-status" in response["Location"]
    assert session.status == ImportSession.Status.FETCHING
    assert session.celery_task_id == "new-task-id"
    assert session.last_error_message == ""
    assert session.last_error_traceback == ""
    assert session.last_failed_stage == ""
    assert session.raw_data == {} or session.raw_data is None
    assert session.normalized_data == {} or session.normalized_data is None
    assert session.authors.count() == 0
    mock_task.delay.assert_called_once_with(session.pk, user.pk)


@pytest.mark.django_db
def test_retry_create_enqueues_create_task_and_clears_record_link(authed_client):
    client, user = authed_client
    session = baker.make(
        ImportSession,
        created_by=user,
        status=ImportSession.Status.IMPORT_FAILED,
        last_failed_stage="create",
        last_error_message="create boom",
        created_record_id=999,
    )

    url = reverse("importer_publikacji:task-retry", kwargs={"session_id": session.pk})

    with patch("importer_publikacji.views.retry.create_publication_task") as mock_task:
        mock_task.delay.return_value.id = "new-task-id-2"
        response = client.post(url)

    session.refresh_from_db()
    assert response.status_code == 302
    assert session.status == ImportSession.Status.CREATING
    assert session.celery_task_id == "new-task-id-2"
    assert session.created_record_id is None
    mock_task.delay.assert_called_once_with(session.pk, user.pk, False)


@pytest.mark.django_db
def test_retry_non_failed_returns_400(authed_client):
    client, user = authed_client
    session = baker.make(
        ImportSession,
        created_by=user,
        status=ImportSession.Status.FETCHED,
    )

    url = reverse("importer_publikacji:task-retry", kwargs={"session_id": session.pk})
    response = client.post(url)

    assert response.status_code == 400


@pytest.mark.django_db
def test_retry_get_returns_405(authed_client):
    client, user = authed_client
    session = baker.make(
        ImportSession,
        created_by=user,
        status=ImportSession.Status.IMPORT_FAILED,
        last_failed_stage="fetch",
    )

    url = reverse("importer_publikacji:task-retry", kwargs={"session_id": session.pk})
    response = client.get(url)

    assert response.status_code == 405


@pytest.mark.django_db
def test_retry_create_respects_persisted_pbn_export_flag(authed_client):
    """Retry musi szanować flag pbn_export_pending z matched_data —
    Task 12 będzie ją persistować gdy user kliknie 'Utwórz + PBN'.
    """
    client, user = authed_client
    session = baker.make(
        ImportSession,
        created_by=user,
        status=ImportSession.Status.IMPORT_FAILED,
        last_failed_stage="create",
        matched_data={"pbn_export_pending": True},
    )

    url = reverse("importer_publikacji:task-retry", kwargs={"session_id": session.pk})

    with patch("importer_publikacji.views.retry.create_publication_task") as mock_task:
        mock_task.delay.return_value.id = "new-task-id-3"
        response = client.post(url)

    assert response.status_code == 302
    mock_task.delay.assert_called_once_with(session.pk, user.pk, True)
