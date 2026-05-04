"""Model tests for pbn_wysylka_oswiadczen app."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from bpp.models import Wydawnictwo_Ciagle
from pbn_wysylka_oswiadczen.models import PbnWysylkaLog, PbnWysylkaOswiadczenTask

User = get_user_model()


@pytest.mark.django_db
def test_pbn_wysylka_oswiadczen_task_model_creation():
    """Test PbnWysylkaOswiadczenTask model creation."""
    user = User.objects.create_user("testuser", password="testpass")

    task = PbnWysylkaOswiadczenTask.objects.create(
        user=user,
        status="running",
        rok_od=2022,
        rok_do=2025,
        total_publications=100,
        processed_publications=50,
    )

    assert task.pk is not None
    assert task.status == "running"
    assert task.rok_od == 2022
    assert task.rok_do == 2025
    assert task.total_publications == 100
    assert task.processed_publications == 50
    assert "Wysyłka oświadczeń" in str(task)


@pytest.mark.django_db
def test_pbn_wysylka_oswiadczen_task_progress_percent():
    """Test progress_percent property."""
    user = User.objects.create_user("testuser", password="testpass")

    # Test with 0 total
    task = PbnWysylkaOswiadczenTask.objects.create(
        user=user, total_publications=0, processed_publications=0
    )
    assert task.progress_percent == 0

    # Test with normal values
    task.total_publications = 100
    task.processed_publications = 50
    task.save()
    assert task.progress_percent == 50

    # Test full progress
    task.processed_publications = 100
    task.save()
    assert task.progress_percent == 100


@pytest.mark.django_db
def test_pbn_wysylka_oswiadczen_task_is_stalled():
    """Test is_stalled method."""
    user = User.objects.create_user("testuser", password="testpass")

    # Running task that's not stalled
    task = PbnWysylkaOswiadczenTask.objects.create(user=user, status="running")
    assert task.is_stalled() is False

    # Manually set last_updated to be older than 15 minutes
    PbnWysylkaOswiadczenTask.objects.filter(pk=task.pk).update(
        last_updated=timezone.now() - timedelta(minutes=20)
    )
    task.refresh_from_db()
    assert task.is_stalled() is True

    # Completed task should not be stalled
    task.status = "completed"
    task.save()
    assert task.is_stalled() is False


@pytest.mark.django_db
def test_pbn_wysylka_oswiadczen_task_get_latest_task():
    """Test get_latest_task class method."""
    user = User.objects.create_user("testuser", password="testpass")

    # No tasks
    assert PbnWysylkaOswiadczenTask.get_latest_task() is None

    # Create tasks
    PbnWysylkaOswiadczenTask.objects.create(user=user, status="completed")
    task2 = PbnWysylkaOswiadczenTask.objects.create(user=user, status="running")

    # Latest should be task2 (most recent)
    latest = PbnWysylkaOswiadczenTask.get_latest_task()
    assert latest == task2


@pytest.mark.django_db
def test_pbn_wysylka_oswiadczen_task_cleanup_stale():
    """Test cleanup_stale_running_tasks class method."""
    user = User.objects.create_user("testuser", password="testpass")

    # Create stale running task
    stale_task = PbnWysylkaOswiadczenTask.objects.create(user=user, status="running")
    PbnWysylkaOswiadczenTask.objects.filter(pk=stale_task.pk).update(
        started_at=timezone.now() - timedelta(hours=25)
    )

    # Create fresh running task
    fresh_task = PbnWysylkaOswiadczenTask.objects.create(user=user, status="running")

    # Run cleanup
    count = PbnWysylkaOswiadczenTask.cleanup_stale_running_tasks()

    assert count == 1
    stale_task.refresh_from_db()
    assert stale_task.status == "failed"
    assert "przestarzalego" in stale_task.error_message

    fresh_task.refresh_from_db()
    assert fresh_task.status == "running"


@pytest.mark.django_db
def test_pbn_wysylka_log_model_creation():
    """Test PbnWysylkaLog model creation."""
    user = User.objects.create_user("testuser", password="testpass")
    task = PbnWysylkaOswiadczenTask.objects.create(user=user)

    content_type = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)

    log = PbnWysylkaLog.objects.create(
        task=task,
        content_type=content_type,
        object_id=123,
        pbn_uid="test-pbn-uid-123",
        status="success",
        json_sent={"test": "data"},
        json_response={"result": "ok"},
    )

    assert log.pk is not None
    assert log.pbn_uid == "test-pbn-uid-123"
    assert log.status == "success"
    assert "test-pbn-uid-123" in str(log)


@pytest.mark.django_db
def test_pbn_wysylka_log_statuses():
    """Test all possible log statuses."""
    user = User.objects.create_user("testuser", password="testpass")
    task = PbnWysylkaOswiadczenTask.objects.create(user=user)
    content_type = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)

    for status in ["success", "error", "skipped", "synchronized", "maintenance"]:
        log = PbnWysylkaLog.objects.create(
            task=task,
            content_type=content_type,
            object_id=1,
            pbn_uid=f"uid-{status}",
            status=status,
        )
        assert log.status == status


@pytest.mark.django_db
def test_pbn_wysylka_task_maintenance_status():
    """Test that maintenance status is available for tasks."""
    user = User.objects.create_user("testuser", password="testpass")
    task = PbnWysylkaOswiadczenTask.objects.create(
        user=user,
        status="maintenance",
        error_message="Prace serwisowe w PBN",
    )
    assert task.status == "maintenance"
    assert "Prace serwisowe" in task.error_message
