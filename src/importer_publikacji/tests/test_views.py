"""Testy widoków importera dotyczące dostępu (uprawnienia), fetcha
identifier-a (`importer_publikacji:fetch`) i anulowania sesji
(`importer_publikacji:cancel`).

Pozostałe widoki wizarda zostały podzielone na osobne pliki:
- `test_views_verify.py` — etap Verify
- `test_views_authors.py` — tworzenie niedopasowanych autorów
- `test_views_create_publication.py` — etap Create + walidacja
- `test_views_helpers.py` — pomocnicze funkcje z views.py
"""

import pytest
from django.urls import reverse

from importer_publikacji.models import ImportSession


@pytest.mark.django_db
def test_index_requires_permission(client):
    """Niezalogowany użytkownik powinien być przekierowany."""
    url = reverse("importer_publikacji:index")
    response = client.get(url)
    assert response.status_code in (302, 403)


@pytest.mark.django_db
def test_index_accessible_for_importer_user(
    importer_client,
):
    url = reverse("importer_publikacji:index")
    response = importer_client.get(url)
    assert response.status_code == 200
    assert "Importer publikacji" in response.content.decode()


@pytest.mark.django_db
def test_index_accessible_for_superuser(db, client):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    superuser = User.objects.create_superuser(
        username="superuser",
        password="pass",
    )
    client.force_login(superuser)
    url = reverse("importer_publikacji:index")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_index_denied_for_staff_user(db, client):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    staff = User.objects.create_user(
        username="staff",
        password="pass",
        is_staff=True,
    )
    client.force_login(staff)
    url = reverse("importer_publikacji:index")
    response = client.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_fetch_empty_identifier(importer_client):
    url = reverse("importer_publikacji:fetch")
    response = importer_client.post(
        url,
        {"provider": "CrossRef", "identifier": ""},
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "wymagane" in content


@pytest.mark.vcr
@pytest.mark.django_db
def test_fetch_invalid_doi(importer_client):
    """normalize_doi("not-a-doi") passes form validation → sesja powstaje
    i task jest enqueueowany. Walidacja samego identyfikatora w formularzu
    nie odrzuca tego inputu, więc widok redirectuje na task-status, gdzie
    polling pokaże wynik (sukces/fail) po wykonaniu task-a.

    Note: mockujemy fetch_session_task.delay żeby uniknąć niedeterministycznej
    propagacji eager-mode (Celery legacy translation CELERY_ALWAYS_EAGER
    nie zawsze daje task_always_eager=False po settings overridach).
    """
    from unittest.mock import patch

    url = reverse("importer_publikacji:fetch")
    with patch("importer_publikacji.views.wizard.fetch_session_task") as mock_task:
        mock_task.delay.return_value.id = "task-uuid"
        response = importer_client.post(
            url,
            {
                "provider": "CrossRef",
                "identifier": "not-a-doi",
            },
        )
    assert response.status_code == 302
    assert "/task-status/" in response["Location"]
    session = ImportSession.objects.get()
    assert session.status == ImportSession.Status.FETCHING
    assert session.celery_task_id != ""


@pytest.mark.django_db
def test_cancel_session(importer_client, importer_user):
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/test",
        raw_data={},
        normalized_data={},
    )
    url = reverse(
        "importer_publikacji:cancel",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.post(url)
    assert response.status_code == 200
    session.refresh_from_db()
    assert session.status == ImportSession.Status.CANCELLED


@pytest.mark.django_db
def test_regular_user_no_access(db, client):
    """Zwykły użytkownik bez grupy nie ma dostępu."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(
        username="regular",
        password="pass",
    )
    client.force_login(user)
    url = reverse("importer_publikacji:index")
    response = client.get(url)
    assert response.status_code in (302, 403)
