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


@pytest.mark.django_db
def test_fetch_view_post_creates_session_with_fetching_status(authed_client):
    client, user = authed_client

    with (
        patch("importer_publikacji.views.wizard.fetch_session_task") as mock_task,
        patch("importer_publikacji.views.wizard.get_provider") as mock_provider,
    ):
        mock_provider.return_value.input_mode = "identifier"
        mock_provider.return_value.validate_identifier.return_value = "10.1234/x"
        mock_task.delay.return_value.id = "task-uuid"

        response = client.post(
            reverse("importer_publikacji:fetch"),
            {"provider": "CrossRef", "identifier": "10.1234/x"},
        )

    sessions = ImportSession.objects.filter(provider_name="CrossRef")
    assert sessions.count() == 1
    session = sessions.first()
    assert session.status == ImportSession.Status.FETCHING
    assert session.celery_task_id == "task-uuid"
    mock_task.delay.assert_called_once_with(session.pk, user.pk)
    assert response.status_code in (200, 302)


@pytest.mark.django_db
def test_fetch_view_post_invalid_identifier_returns_form_error(authed_client):
    client, _ = authed_client

    with patch("importer_publikacji.views.wizard.get_provider") as mock_provider:
        mock_provider.return_value.input_mode = "identifier"
        mock_provider.return_value.validate_identifier.return_value = None

        response = client.post(
            reverse("importer_publikacji:fetch"),
            {"provider": "CrossRef", "identifier": "garbage"},
        )

    assert response.status_code == 200
    assert ImportSession.objects.count() == 0


@pytest.mark.django_db
def test_fetch_view_post_does_not_call_provider_fetch_inline(authed_client):
    """View must NOT call provider.fetch() inline — that work belongs to the task."""
    client, _ = authed_client

    with (
        patch("importer_publikacji.views.wizard.fetch_session_task") as mock_task,
        patch("importer_publikacji.views.wizard.get_provider") as mock_provider,
    ):
        mock_provider.return_value.input_mode = "identifier"
        mock_provider.return_value.validate_identifier.return_value = "10.1234/x"
        mock_task.delay.return_value.id = "task-uuid"

        client.post(
            reverse("importer_publikacji:fetch"),
            {"provider": "CrossRef", "identifier": "10.1234/x"},
        )

    mock_provider.return_value.fetch.assert_not_called()
    mock_task.delay.assert_called_once()


@pytest.mark.django_db
def test_fetch_view_post_redirects_to_in_flight_session(authed_client):
    """Double-click defense: ponowny POST tego samego DOI redirectuje
    do juz-istniejacej sesji zamiast startowac nowego taska."""
    client, user = authed_client
    existing = baker.make(
        ImportSession,
        created_by=user,
        provider_name="CrossRef",
        identifier="10.1234/x",
        status=ImportSession.Status.FETCHING,
    )

    with (
        patch("importer_publikacji.views.wizard.fetch_session_task") as mock_task,
        patch("importer_publikacji.views.wizard.get_provider") as mock_provider,
    ):
        from importer_publikacji.providers import InputMode

        mock_provider.return_value.input_mode = InputMode.IDENTIFIER
        mock_provider.return_value.validate_identifier.return_value = "10.1234/x"

        response = client.post(
            reverse("importer_publikacji:fetch"),
            {"provider": "CrossRef", "identifier": "10.1234/x"},
        )

    # Brak nowej sesji
    assert ImportSession.objects.filter(provider_name="CrossRef").count() == 1
    # Brak nowego taska
    mock_task.delay.assert_not_called()
    # Redirect do istniejacej sesji
    assert response.status_code == 302
    assert str(existing.pk) in response["Location"]


@pytest.mark.django_db
def test_fetch_view_post_accepts_long_text_identifier(authed_client):
    """Regression: BibTeX entries can exceed 255 chars.

    Identifier field must accept long text inputs.
    """
    client, user = authed_client

    long_bibtex = (
        "@article{key2024test,\n"
        + ("  abstract = {" + "Lorem ipsum dolor sit amet. " * 50 + "},\n")
        + "}"
    )
    assert len(long_bibtex) > 255

    with (
        patch("importer_publikacji.views.wizard.fetch_session_task") as mock_task,
        patch("importer_publikacji.views.wizard.get_provider") as mock_provider,
    ):
        from importer_publikacji.providers import InputMode

        mock_provider.return_value.input_mode = InputMode.TEXT
        mock_provider.return_value.validate_identifier.return_value = long_bibtex
        mock_task.delay.return_value.id = "task-id"

        response = client.post(
            reverse("importer_publikacji:fetch"),
            {"provider": "BibTeX", "text_input": long_bibtex},
        )

    assert response.status_code == 302
    session = ImportSession.objects.first()
    assert session is not None
    assert session.identifier == long_bibtex
