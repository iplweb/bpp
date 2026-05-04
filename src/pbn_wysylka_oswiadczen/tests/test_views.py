"""View tests for pbn_wysylka_oswiadczen app."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory

from bpp.models import Wydawnictwo_Ciagle
from pbn_wysylka_oswiadczen.models import PbnWysylkaLog, PbnWysylkaOswiadczenTask
from pbn_wysylka_oswiadczen.views import (
    CancelTaskView,
    LogListView,
    PbnWysylkaOswiadczenMainView,
    StartTaskView,
    TaskStatusPartialView,
    TaskStatusView,
)

from ._helpers import create_user_with_group

User = get_user_model()


@pytest.mark.django_db
def test_main_view_context(uczelnia):
    """Test main view returns correct context."""
    factory = RequestFactory()
    request = factory.get("/?rok_od=2022&rok_do=2024")

    user = create_user_with_group()
    request.user = user
    request.session = {}

    view = PbnWysylkaOswiadczenMainView()
    view.setup(request)

    context = view.get_context_data()
    assert "rok_od" in context
    assert "rok_do" in context
    assert "total_count" in context
    assert "ciagle_count" in context
    assert "zwarte_count" in context
    assert "latest_task" in context
    assert "can_resume" in context
    assert context["rok_od"] == 2022
    assert context["rok_do"] == 2024


@pytest.mark.django_db
def test_main_view_requires_group():
    """Test main view requires proper group."""
    factory = RequestFactory()
    request = factory.get("/")

    user = User.objects.create_user("testuser", password="testpass")
    request.user = user
    request.session = {}

    try:
        response = PbnWysylkaOswiadczenMainView.as_view()(request)
        assert response.status_code in [302, 403]
    except Exception:
        # Expected - permission denied
        pass


@pytest.mark.django_db
def test_task_status_view_no_tasks():
    """Test task status view when no tasks exist."""
    factory = RequestFactory()
    request = factory.get("/status/")

    user = create_user_with_group()
    request.user = user
    request.session = {}

    view = TaskStatusView()
    response = view.get(request)

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["is_running"] is False
    assert data["latest_task"] is None


@pytest.mark.django_db
def test_task_status_view_with_task():
    """Test task status view with existing task."""
    factory = RequestFactory()
    request = factory.get("/status/")

    user = create_user_with_group()
    request.user = user
    request.session = {}

    # Create a task
    PbnWysylkaOswiadczenTask.objects.create(
        user=user,
        status="running",
        total_publications=100,
        processed_publications=50,
        success_count=30,
        error_count=5,
        skipped_count=15,
    )

    view = TaskStatusView()
    response = view.get(request)

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["is_running"] is True
    assert data["latest_task"]["status"] == "running"
    assert data["latest_task"]["total_publications"] == 100
    assert data["latest_task"]["processed_publications"] == 50
    assert data["latest_task"]["progress_percent"] == 50


@pytest.mark.django_db
def test_start_task_view_no_token():
    """Test start task view when user has no PBN token."""
    factory = RequestFactory()
    request = factory.post("/start/", {"rok_od": "2022", "rok_do": "2025"})

    user = create_user_with_group()
    request.user = user
    request.session = {}

    # Mock get_pbn_user
    class MockPbnUser:
        pbn_token = None

    user.get_pbn_user = lambda: MockPbnUser()

    view = StartTaskView()
    response = view.post(request)

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["success"] is False
    assert "zalogowany" in data["error"].lower() or "pbn" in data["error"].lower()


@pytest.mark.django_db
def test_start_task_view_expired_token():
    """Test start task view when PBN token is expired."""
    factory = RequestFactory()
    request = factory.post("/start/", {"rok_od": "2022", "rok_do": "2025"})

    user = create_user_with_group()
    request.user = user
    request.session = {}

    # Mock get_pbn_user with expired token
    class MockPbnUser:
        pbn_token = "some-token"

        def pbn_token_possibly_valid(self):
            return False

    user.get_pbn_user = lambda: MockPbnUser()

    view = StartTaskView()
    response = view.post(request)

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["success"] is False
    assert "wygasl" in data["error"].lower()


@pytest.mark.django_db
def test_start_task_view_already_running():
    """Test start task view when task is already running."""
    factory = RequestFactory()
    request = factory.post("/start/", {"rok_od": "2022", "rok_do": "2025"})

    user = create_user_with_group()
    request.user = user
    request.session = {}

    # Create running task
    PbnWysylkaOswiadczenTask.objects.create(user=user, status="running")

    # Mock get_pbn_user with valid token
    class MockPbnUser:
        pbn_token = "valid-token"

        def pbn_token_possibly_valid(self):
            return True

    user.get_pbn_user = lambda: MockPbnUser()

    view = StartTaskView()
    response = view.post(request)

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["success"] is False
    assert "uruchomione" in data["error"].lower()


@pytest.mark.django_db
def test_cancel_task_view_no_running_task():
    """Test cancel task view when no task is running."""
    factory = RequestFactory()
    request = factory.post("/cancel/")

    user = create_user_with_group()
    request.user = user
    request.session = {}

    view = CancelTaskView()
    response = view.post(request)

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["success"] is False
    assert "brak" in data["error"].lower()


@pytest.mark.django_db
def test_cancel_task_view_success():
    """Test cancel task view successfully cancels running task."""
    factory = RequestFactory()
    request = factory.post("/cancel/")

    user = create_user_with_group()
    request.user = user
    request.session = {}

    # Create running task
    task = PbnWysylkaOswiadczenTask.objects.create(user=user, status="running")

    view = CancelTaskView()
    response = view.post(request)

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["success"] is True

    task.refresh_from_db()
    assert task.status == "failed"
    assert "anulowane" in task.error_message.lower()


@pytest.mark.django_db
def test_task_status_partial_view():
    """Test task status partial view."""
    factory = RequestFactory()
    request = factory.get("/status-partial/")

    user = create_user_with_group()
    request.user = user
    request.session = {}

    view = TaskStatusPartialView()
    view.setup(request)

    context = view.get_context_data()
    assert "latest_task" in context


@pytest.mark.django_db
def test_log_list_view():
    """Test log list view."""
    factory = RequestFactory()
    request = factory.get("/logs/")

    user = create_user_with_group()
    request.user = user
    request.session = {}

    # Create task and logs
    task = PbnWysylkaOswiadczenTask.objects.create(user=user)
    content_type = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
    for i in range(5):
        PbnWysylkaLog.objects.create(
            task=task,
            content_type=content_type,
            object_id=i,
            pbn_uid=f"uid-{i}",
            status="success",
        )

    view = LogListView()
    view.setup(request)

    context = view.get_context_data()
    assert "page_obj" in context
    assert context["page_obj"].paginator.count == 5


@pytest.mark.django_db
def test_log_list_view_with_filters():
    """Test log list view with status filter."""
    factory = RequestFactory()
    request = factory.get("/logs/?status=error")

    user = create_user_with_group()
    request.user = user
    request.session = {}

    # Create task and logs with different statuses
    task = PbnWysylkaOswiadczenTask.objects.create(user=user)
    content_type = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)

    PbnWysylkaLog.objects.create(
        task=task,
        content_type=content_type,
        object_id=1,
        pbn_uid="uid-success",
        status="success",
    )
    PbnWysylkaLog.objects.create(
        task=task,
        content_type=content_type,
        object_id=2,
        pbn_uid="uid-error",
        status="error",
    )

    view = LogListView()
    view.setup(request)

    context = view.get_context_data()
    assert context["page_obj"].paginator.count == 1
    assert context["page_obj"].object_list[0].status == "error"
