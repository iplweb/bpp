"""Tests for Celery tasks in komparator_pbn_udzialy application."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.django_db
def test_porownaj_dyscypliny_pbn_task_success():
    """Test that porownaj_dyscypliny_pbn_task executes successfully."""
    from komparator_pbn_udzialy.tasks import porownaj_dyscypliny_pbn_task

    with patch("komparator_pbn_udzialy.tasks.cache"):
        with patch(
            "komparator_pbn_udzialy.tasks.KomparatorDyscyplinPBN"
        ) as mock_komparator:
            mock_instance = MagicMock()
            mock_instance.stats = {"processed": 10, "discrepancies_found": 2}
            mock_instance.run.return_value = mock_instance.stats
            mock_komparator.return_value = mock_instance

            result = porownaj_dyscypliny_pbn_task.apply(args=(False,)).result

            assert result["status"] == "SUCCESS"
            assert "stats" in result


@pytest.mark.django_db
def test_porownaj_dyscypliny_pbn_task_progress_tracking():
    """Test that porownaj_dyscypliny_pbn_task updates progress via cache."""
    from komparator_pbn_udzialy.tasks import porownaj_dyscypliny_pbn_task

    cache_calls = []

    def track_cache_set(key, value, timeout):
        cache_calls.append({"key": key, "value": value})

    with patch("komparator_pbn_udzialy.tasks.cache") as mock_cache:
        mock_cache.set.side_effect = track_cache_set

        with patch(
            "komparator_pbn_udzialy.tasks.KomparatorDyscyplinPBN"
        ) as mock_komparator:
            mock_instance = MagicMock()
            mock_instance.stats = {"processed": 0, "discrepancies_found": 0}
            mock_instance.run.return_value = mock_instance.stats
            mock_komparator.return_value = mock_instance

            porownaj_dyscypliny_pbn_task.apply(args=(False,))

    # Cache should have been called at least for init and success
    assert len(cache_calls) >= 2


@pytest.mark.django_db
def test_get_task_status_pending():
    """Test get_task_status returns pending for unknown task."""
    from komparator_pbn_udzialy.tasks import get_task_status

    with patch("komparator_pbn_udzialy.tasks.cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch("komparator_pbn_udzialy.tasks.AsyncResult") as mock_result:
            mock_task = MagicMock()
            mock_task.state = "PENDING"
            mock_result.return_value = mock_task

            status = get_task_status("fake-task-id")

    assert status["status"] == "PENDING"


@pytest.mark.django_db
def test_get_task_status_from_cache():
    """Test get_task_status returns cached status."""
    from komparator_pbn_udzialy.tasks import get_task_status

    cached_status = {
        "status": "PROGRESS",
        "current": 5,
        "total": 10,
        "stats": {"processed": 5},
    }

    with patch("komparator_pbn_udzialy.tasks.cache") as mock_cache:
        mock_cache.get.return_value = cached_status

        status = get_task_status("cached-task-id")

    assert status == cached_status


@pytest.mark.django_db
def test_get_task_status_success():
    """Test get_task_status returns success state."""
    from komparator_pbn_udzialy.tasks import get_task_status

    with patch("komparator_pbn_udzialy.tasks.cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch("komparator_pbn_udzialy.tasks.AsyncResult") as mock_result:
            mock_task = MagicMock()
            mock_task.state = "SUCCESS"
            mock_task.info = {"message": "Done", "stats": {"processed": 100}}
            mock_result.return_value = mock_task

            status = get_task_status("success-task-id")

    assert status["status"] == "SUCCESS"


@pytest.mark.django_db
def test_get_task_status_failure():
    """Test get_task_status returns failure state."""
    from komparator_pbn_udzialy.tasks import get_task_status

    with patch("komparator_pbn_udzialy.tasks.cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch("komparator_pbn_udzialy.tasks.AsyncResult") as mock_result:
            mock_task = MagicMock()
            mock_task.state = "FAILURE"
            mock_task.info = "Error message"
            mock_result.return_value = mock_task

            status = get_task_status("failure-task-id")

    assert status["status"] == "FAILURE"
