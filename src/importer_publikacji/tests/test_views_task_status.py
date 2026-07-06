from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
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
def fetching_session(db, authed_client):
    _, user = authed_client
    return baker.make(
        ImportSession,
        created_by=user,
        status=ImportSession.Status.FETCHING,
        celery_task_id="task-uuid-1",
    )


@pytest.mark.django_db
def test_task_status_get_renders_progress_partial_for_htmx(
    authed_client, fetching_session
):
    client, _ = authed_client
    url = reverse(
        "importer_publikacji:task-status",
        kwargs={"session_id": fetching_session.pk},
    )

    with patch("importer_publikacji.views.task_status.AsyncResult") as mock_async:
        mock_async.return_value = MagicMock(
            info={
                "stage_code": "match_authors",
                "label": "Dopasowuję autorów...",
                "current": 5,
                "total": 50,
                "counter_display": "5/50",
                "progress": 30,
            }
        )

        response = client.get(url, HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert b"Dopasowuj" in response.content
    assert b"30" in response.content


@pytest.mark.django_db
def test_task_status_get_renders_full_page_for_non_htmx(
    authed_client, fetching_session
):
    client, _ = authed_client
    url = reverse(
        "importer_publikacji:task-status",
        kwargs={"session_id": fetching_session.pk},
    )

    with patch("importer_publikacji.views.task_status.AsyncResult") as mock_async:
        mock_async.return_value = MagicMock(info={"progress": 50})
        response = client.get(url)

    assert response.status_code == 200
    assert (
        b"<html" in response.content.lower() or b"step_task_status" in response.content
    )


@pytest.mark.django_db
def test_task_status_terminal_status_redirects_with_hx_redirect(
    authed_client, fetching_session
):
    client, _ = authed_client
    fetching_session.status = ImportSession.Status.FETCHED
    fetching_session.celery_task_id = ""
    fetching_session.save()

    url = reverse(
        "importer_publikacji:task-status",
        kwargs={"session_id": fetching_session.pk},
    )
    response = client.get(url, HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert "HX-Redirect" in response.headers
    assert "verify" in response.headers["HX-Redirect"]


@pytest.mark.django_db
def test_task_status_failed_renders_error_partial(authed_client, fetching_session):
    client, user = authed_client
    fetching_session.status = ImportSession.Status.IMPORT_FAILED
    fetching_session.last_error_message = "Nie udało się pobrać"
    fetching_session.last_error_traceback = "Traceback..."
    fetching_session.last_failed_stage = "fetch"
    fetching_session.save()

    url = reverse(
        "importer_publikacji:task-status",
        kwargs={"session_id": fetching_session.pk},
    )
    response = client.get(url, HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert b"Nie uda" in response.content
    assert b"Traceback" in response.content


@pytest.mark.django_db
def test_task_status_failed_hides_traceback_from_non_superuser(
    client, django_user_model
):
    user = baker.make(django_user_model, is_staff=True, is_superuser=False)
    user.set_password("test")
    user.save()
    # Non-superuser still needs importer group permission to access the view.
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(group)
    client.force_login(user)

    session = baker.make(
        ImportSession,
        created_by=user,
        status=ImportSession.Status.IMPORT_FAILED,
        last_error_message="User msg",
        last_error_traceback="secret traceback",
    )

    url = reverse(
        "importer_publikacji:task-status",
        kwargs={"session_id": session.pk},
    )
    response = client.get(url, HTTP_HX_REQUEST="true")

    assert b"User msg" in response.content
    assert b"secret traceback" not in response.content


@pytest.mark.django_db
def test_task_status_pending_renders_initialization_message(
    authed_client, fetching_session
):
    client, _ = authed_client
    url = reverse(
        "importer_publikacji:task-status",
        kwargs={"session_id": fetching_session.pk},
    )

    with patch("importer_publikacji.views.task_status.AsyncResult") as mock_async:
        mock_async.return_value = MagicMock(info=None)

        response = client.get(url, HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert b"Inicjalizacja" in response.content or b"Trwa" in response.content


@pytest.mark.django_db
def test_task_status_stalled_fetching_session_marked_failed(
    authed_client, fetching_session
):
    """Watchdog: sesja tkwiąca w FETCHING dłużej niż próg zostaje przy
    kolejnym pollu przełączona na IMPORT_FAILED (bez tego wisiała wiecznie,
    bo martwy/zgubiony worker nie wykonuje bloku except taska — FD).
    """
    client, _ = authed_client
    # Cofnij `modified` poza próg watchdoga. `.update()` omija auto_now,
    # inaczej save nadpisałby modified na "teraz".
    stale = timezone.now() - timedelta(seconds=10_000)
    ImportSession.objects.filter(pk=fetching_session.pk).update(modified=stale)

    url = reverse(
        "importer_publikacji:task-status",
        kwargs={"session_id": fetching_session.pk},
    )
    response = client.get(url, HTTP_HX_REQUEST="true")

    fetching_session.refresh_from_db()
    assert fetching_session.status == ImportSession.Status.IMPORT_FAILED
    assert fetching_session.last_failed_stage == "fetch"
    assert fetching_session.celery_task_id == ""
    assert response.status_code == 200
    # Ekran błędu z komunikatem watchdoga ("...trwała zbyt długo...").
    assert b"zbyt d" in response.content


@pytest.mark.django_db
def test_task_status_fresh_fetching_not_marked_stalled(authed_client, fetching_session):
    """Świeża sesja FETCHING (poniżej progu) NIE jest ubijana — dalej
    renderujemy progress. Ochrona przed false-positive watchdoga.
    """
    client, _ = authed_client
    url = reverse(
        "importer_publikacji:task-status",
        kwargs={"session_id": fetching_session.pk},
    )

    with patch("importer_publikacji.views.task_status.AsyncResult") as mock_async:
        mock_async.return_value = MagicMock(
            info={"progress": 10, "label": "Pobieram dane od dostawcy..."}
        )
        response = client.get(url, HTTP_HX_REQUEST="true")

    fetching_session.refresh_from_db()
    assert fetching_session.status == ImportSession.Status.FETCHING
    assert response.status_code == 200


@pytest.mark.django_db
def test_task_status_cancelled_redirects_to_index(authed_client):
    client, user = authed_client
    session = baker.make(
        ImportSession,
        created_by=user,
        status=ImportSession.Status.CANCELLED,
    )

    url = reverse(
        "importer_publikacji:task-status",
        kwargs={"session_id": session.pk},
    )
    response = client.get(url, HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert "HX-Redirect" in response.headers
    # Powinien przekierowac do index, nie do literal "None"
    assert response.headers["HX-Redirect"].endswith(
        reverse("importer_publikacji:index")
    )
    assert "None" not in response.headers["HX-Redirect"]
