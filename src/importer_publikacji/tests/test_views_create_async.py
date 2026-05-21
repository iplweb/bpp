from unittest.mock import patch

import pytest
from django.urls import reverse
from model_bakery import baker

from importer_publikacji.models import ImportSession


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


@pytest.fixture
def review_session(authed_client):
    _, user = authed_client
    return baker.make(
        ImportSession,
        created_by=user,
        status=ImportSession.Status.REVIEW,
    )


@pytest.mark.django_db
def test_create_view_post_enqueues_task_and_marks_creating(
    authed_client, review_session
):
    client, user = authed_client

    with patch("importer_publikacji.views.wizard.create_publication_task") as mock_task:
        mock_task.delay.return_value.id = "create-task-uuid"
        url = reverse(
            "importer_publikacji:create",
            kwargs={"session_id": review_session.pk},
        )
        response = client.post(url, {})

    review_session.refresh_from_db()
    assert review_session.status == ImportSession.Status.CREATING
    assert review_session.celery_task_id == "create-task-uuid"
    mock_task.delay.assert_called_once_with(review_session.pk, user.pk, False)
    assert response.status_code == 302


@pytest.mark.django_db
def test_create_view_post_with_pbn_flag_passes_true(authed_client, review_session):
    client, _ = authed_client

    with patch("importer_publikacji.views.wizard.create_publication_task") as mock_task:
        mock_task.delay.return_value.id = "create-task-uuid"
        url = reverse(
            "importer_publikacji:create",
            kwargs={"session_id": review_session.pk},
        )
        client.post(url, {"_create_and_pbn": "1"})

    args = mock_task.delay.call_args.args
    assert args[2] is True  # also_pbn=True


@pytest.mark.django_db
def test_create_view_post_persists_pbn_export_pending_to_matched_data(
    authed_client, review_session
):
    """Task 10 retry reads session.matched_data['pbn_export_pending'] to
    honor the original PBN choice on retry. Task 12 must persist it."""
    client, _ = authed_client

    with patch("importer_publikacji.views.wizard.create_publication_task") as mock_task:
        mock_task.delay.return_value.id = "create-task-uuid"
        url = reverse(
            "importer_publikacji:create",
            kwargs={"session_id": review_session.pk},
        )
        client.post(url, {"_create_and_pbn": "1"})

    review_session.refresh_from_db()
    assert review_session.matched_data.get("pbn_export_pending") is True


@pytest.mark.django_db
def test_create_view_post_persists_pbn_export_pending_false(
    authed_client, review_session
):
    """Without _create_and_pbn flag, matched_data['pbn_export_pending']
    should be False (not unset)."""
    client, _ = authed_client

    with patch("importer_publikacji.views.wizard.create_publication_task") as mock_task:
        mock_task.delay.return_value.id = "create-task-uuid"
        url = reverse(
            "importer_publikacji:create",
            kwargs={"session_id": review_session.pk},
        )
        client.post(url, {})

    review_session.refresh_from_db()
    assert review_session.matched_data.get("pbn_export_pending") is False
