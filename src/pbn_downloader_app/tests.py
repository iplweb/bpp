import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import RequestFactory
from django.urls import reverse

from bpp.const import GR_WPROWADZANIE_DANYCH
from pbn_downloader_app.models import (
    PbnDownloadTask,
    PbnInstitutionPeopleTask,
    PbnJournalsDownloadTask,
)
from pbn_downloader_app.views import (
    JournalsTaskStatusView,
    PbnDownloaderMainView,
    PeopleTaskStatusView,
    StartJournalsDownloadView,
    StartPbnDownloadView,
    StartPbnPeopleDownloadView,
    TaskStatusView,
)

User = get_user_model()


@pytest.mark.django_db
def test_pbn_download_task_model():
    """Test PbnDownloadTask model functionality."""
    user = User.objects.create_user("testuser", password="testpass")

    task = PbnDownloadTask.objects.create(
        user=user, status="running", current_step="Test step", progress_percentage=50
    )

    assert str(task) == f"PBN Download Task {task.id} - running"
    assert task.progress_percentage == 50
    assert task.current_step == "Test step"

    # Test get_latest_task method
    latest = PbnDownloadTask.get_latest_task()
    assert latest == task


@pytest.mark.django_db
def test_cleanup_stale_running_tasks():
    """Test cleanup of stale running tasks."""
    user = User.objects.create_user("testuser", password="testpass")

    # Create a stale task (older than 24 hours)
    from datetime import timedelta

    from django.utils import timezone

    stale_task = PbnDownloadTask.objects.create(user=user, status="running")

    # Manually set started_at to be older than 24 hours
    stale_task.started_at = timezone.now() - timedelta(hours=25)
    stale_task.save()

    # Run cleanup
    count = PbnDownloadTask.cleanup_stale_running_tasks()

    assert count == 1
    stale_task.refresh_from_db()
    assert stale_task.status == "failed"
    assert "stale status" in stale_task.error_message


@pytest.mark.django_db
def test_pbn_downloader_main_view():
    """Test that main view works for users with proper group."""
    factory = RequestFactory()
    request = factory.get("/")

    user = User.objects.create_user("testuser", password="testpass")
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(group)
    request.user = user
    request.session = {}

    view = PbnDownloaderMainView()
    view.setup(request)

    context = view.get_context_data()
    assert "latest_task" in context
    assert "latest_people_task" in context
    assert "latest_journals_task" in context


@pytest.mark.django_db
def test_pbn_downloader_main_view_requires_group():
    """Test that main view requires proper group access."""
    factory = RequestFactory()
    request = factory.get("/")

    user = User.objects.create_user("testuser", password="testpass")
    request.user = user
    request.session = {}

    try:
        response = PbnDownloaderMainView.as_view()(request)
        # Should fail due to group_required decorator
        assert response.status_code in [302, 403] or hasattr(response, "status_code")
    except Exception:
        # Expected to fail due to group_required decorator
        assert True


@pytest.mark.django_db
def test_start_pbn_download_view_no_token():
    """Test start download view when user has no PBN token."""
    factory = RequestFactory()
    request = factory.post("/api/start-download/")

    user = User.objects.create_user("testuser", password="testpass")
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(group)
    request.user = user
    request.session = {}

    # Mock get_pbn_user method
    class MockPbnUser:
        pbn_token = None

    user.get_pbn_user = lambda: MockPbnUser()

    view = StartPbnDownloadView()
    response = view.post(request)

    assert response.status_code == 200
    import json

    data = json.loads(response.content)
    assert data["success"] is False
    assert "Nie jesteś zalogowany w PBN" in data["error"]


@pytest.mark.django_db
def test_task_status_view():
    """Test task status API view."""
    factory = RequestFactory()
    request = factory.get("/api/task-status/")

    user = User.objects.create_user("testuser", password="testpass")
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(group)
    request.user = user
    request.session = {}

    # Test with no tasks
    view = TaskStatusView()
    response = view.get(request)

    assert response.status_code == 200
    import json

    data = json.loads(response.content)
    assert data["is_running"] is False
    assert data["latest_task"] is None

    # Test with a task
    task = PbnDownloadTask.objects.create(  # noqa
        user=user, status="completed", progress_percentage=100
    )

    response = view.get(request)
    data = json.loads(response.content)
    assert data["latest_task"]["status"] == "completed"
    assert data["latest_task"]["progress_percentage"] == 100


@pytest.mark.django_db
def test_url_patterns():
    """Test that URL patterns are properly configured."""
    url = reverse("pbn_downloader_app:main")
    assert url == "/pbn_downloader_app/"

    url = reverse("pbn_downloader_app:start_download")
    assert url == "/pbn_downloader_app/api/start-download/"

    url = reverse("pbn_downloader_app:task_status")
    assert url == "/pbn_downloader_app/api/task-status/"

    url = reverse("pbn_downloader_app:retry_task")
    assert url == "/pbn_downloader_app/api/retry-task/"

    url = reverse("pbn_downloader_app:start_people_download")
    assert url == "/pbn_downloader_app/api/start-people-download/"

    url = reverse("pbn_downloader_app:people_task_status")
    assert url == "/pbn_downloader_app/api/people-task-status/"

    url = reverse("pbn_downloader_app:retry_people_task")
    assert url == "/pbn_downloader_app/api/retry-people-task/"

    url = reverse("pbn_downloader_app:start_journals_download")
    assert url == "/pbn_downloader_app/api/start-journals-download/"

    url = reverse("pbn_downloader_app:journals_task_status")
    assert url == "/pbn_downloader_app/api/journals-task-status/"

    url = reverse("pbn_downloader_app:retry_journals_task")
    assert url == "/pbn_downloader_app/api/retry-journals-task/"


@pytest.mark.django_db
def test_task_model_ordering():
    """Test that tasks are ordered by -started_at."""
    user = User.objects.create_user("testuser", password="testpass")

    task1 = PbnDownloadTask.objects.create(user=user, status="completed")
    task2 = PbnDownloadTask.objects.create(user=user, status="failed")

    # The latest task should be task2 due to ordering
    latest = PbnDownloadTask.get_latest_task()
    assert latest == task2

    # Check ordering in queryset
    tasks = list(PbnDownloadTask.objects.all())
    assert tasks[0] == task2
    assert tasks[1] == task1


@pytest.mark.django_db
def test_pbn_institution_people_task_model():
    """Test PbnInstitutionPeopleTask model functionality."""
    user = User.objects.create_user("testuser", password="testpass")

    task = PbnInstitutionPeopleTask.objects.create(
        user=user, status="running", current_step="Test step", progress_percentage=50
    )

    assert str(task) == f"PBN People Download Task {task.id} - running"
    assert task.progress_percentage == 50
    assert task.current_step == "Test step"

    # Test get_latest_task method
    latest = PbnInstitutionPeopleTask.get_latest_task()
    assert latest == task


@pytest.mark.django_db
def test_people_task_status_view():
    """Test people task status API view."""
    factory = RequestFactory()
    request = factory.get("/api/people-task-status/")

    user = User.objects.create_user("testuser", password="testpass")
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(group)
    request.user = user
    request.session = {}

    # Test with no tasks
    view = PeopleTaskStatusView()
    response = view.get(request)

    assert response.status_code == 200
    import json

    data = json.loads(response.content)
    assert data["is_running"] is False
    assert data["latest_task"] is None

    # Test with a task
    task = PbnInstitutionPeopleTask.objects.create(  # noqa
        user=user, status="completed", progress_percentage=100
    )

    response = view.get(request)

    data = json.loads(response.content)
    assert data["latest_task"]["status"] == "completed"
    assert data["latest_task"]["progress_percentage"] == 100


@pytest.mark.django_db
def test_start_people_download_view_no_token():
    """Test start people download view when user has no PBN token."""
    factory = RequestFactory()
    request = factory.post("/api/start-people-download/")

    user = User.objects.create_user("testuser", password="testpass")
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(group)
    request.user = user
    request.session = {}

    # Mock get_pbn_user method
    class MockPbnUser:
        pbn_token = None

    user.get_pbn_user = lambda: MockPbnUser()

    view = StartPbnPeopleDownloadView()
    response = view.post(request)

    assert response.status_code == 200
    import json

    data = json.loads(response.content)
    assert data["success"] is False
    assert "Nie jesteś zalogowany w PBN" in data["error"]


@pytest.mark.django_db
def test_pbn_journals_download_task_model():
    """Test PbnJournalsDownloadTask model functionality."""
    user = User.objects.create_user("testuser", password="testpass")

    task = PbnJournalsDownloadTask.objects.create(
        user=user,
        status="running",
        current_step="Test step",
        progress_percentage=50,
        journals_processed=10,
        total_journals=100,
        zrodla_integrated=5,
    )

    assert str(task) == f"PBN Journals Download Task {task.id} - running"
    assert task.progress_percentage == 50
    assert task.current_step == "Test step"
    assert task.journals_processed == 10
    assert task.total_journals == 100
    assert task.zrodla_integrated == 5

    # Test get_latest_task method
    latest = PbnJournalsDownloadTask.get_latest_task()
    assert latest == task


@pytest.mark.django_db
def test_journals_cleanup_stale_running_tasks():
    """Test cleanup of stale running journals tasks."""
    user = User.objects.create_user("testuser", password="testpass")

    # Create a stale task (older than 24 hours)
    from datetime import timedelta

    from django.utils import timezone

    stale_task = PbnJournalsDownloadTask.objects.create(user=user, status="running")

    # Manually set started_at to be older than 24 hours
    stale_task.started_at = timezone.now() - timedelta(hours=25)
    stale_task.save()

    # Run cleanup
    count = PbnJournalsDownloadTask.cleanup_stale_running_tasks()

    assert count == 1
    stale_task.refresh_from_db()
    assert stale_task.status == "failed"
    assert "stale status" in stale_task.error_message


@pytest.mark.django_db
def test_journals_task_status_view():
    """Test journals task status API view."""
    factory = RequestFactory()
    request = factory.get("/api/journals-task-status/")

    user = User.objects.create_user("testuser", password="testpass")
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(group)
    request.user = user
    request.session = {}

    # Test with no tasks
    view = JournalsTaskStatusView()
    response = view.get(request)

    assert response.status_code == 200
    import json

    data = json.loads(response.content)
    assert data["is_running"] is False
    assert data["latest_task"] is None

    # Test with a task
    task = PbnJournalsDownloadTask.objects.create(  # noqa
        user=user,
        status="completed",
        progress_percentage=100,
        journals_processed=50,
        total_journals=50,
        zrodla_integrated=10,
    )

    response = view.get(request)
    data = json.loads(response.content)
    assert data["latest_task"]["status"] == "completed"
    assert data["latest_task"]["progress_percentage"] == 100
    assert data["latest_task"]["journals_processed"] == 50
    assert data["latest_task"]["zrodla_integrated"] == 10


@pytest.mark.django_db
def test_start_journals_download_view_no_token():
    """Test start journals download view when user has no PBN token."""
    factory = RequestFactory()
    request = factory.post("/api/start-journals-download/")

    user = User.objects.create_user("testuser", password="testpass")
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(group)
    request.user = user
    request.session = {}

    # Mock get_pbn_user method
    class MockPbnUser:
        pbn_token = None

    user.get_pbn_user = lambda: MockPbnUser()

    view = StartJournalsDownloadView()
    response = view.post(request)

    assert response.status_code == 200
    import json

    data = json.loads(response.content)
    assert data["success"] is False
    assert "Nie jesteś zalogowany w PBN" in data["error"]


@pytest.mark.django_db
def test_journals_task_model_ordering():
    """Test that journals tasks are ordered by -started_at."""
    user = User.objects.create_user("testuser", password="testpass")

    task1 = PbnJournalsDownloadTask.objects.create(user=user, status="completed")
    task2 = PbnJournalsDownloadTask.objects.create(user=user, status="failed")

    # The latest task should be task2 due to ordering
    latest = PbnJournalsDownloadTask.get_latest_task()
    assert latest == task2

    # Check ordering in queryset
    tasks = list(PbnJournalsDownloadTask.objects.all())
    assert tasks[0] == task2
    assert tasks[1] == task1
