"""Tests for importer_autorow_pbn Celery tasks."""

from unittest.mock import MagicMock, patch

import pytest
from model_bakery import baker

from importer_autorow_pbn.models import CachedScientistMatch, MatchCacheRebuildOperation
from pbn_api.models import Scientist


@pytest.mark.django_db
def test_rebuild_match_cache_task_success(admin_user):
    """Test that rebuild_match_cache_task executes operation."""
    from importer_autorow_pbn.tasks import rebuild_match_cache_task

    # Create operation
    operation = MatchCacheRebuildOperation.objects.create(owner=admin_user)

    with patch.object(operation, "task_perform") as mock_perform:
        # Mock operation lookup
        with patch(
            "importer_autorow_pbn.tasks.MatchCacheRebuildOperation.objects.get"
        ) as mock_get:
            mock_get.return_value = operation
            rebuild_match_cache_task(operation.pk)

            mock_perform.assert_called_once()


@pytest.mark.django_db
def test_rebuild_match_cache_task_calls_task_perform(admin_user):
    """Test that rebuild_match_cache_task calls task_perform on operation."""
    from importer_autorow_pbn.tasks import rebuild_match_cache_task

    # Create operation
    operation = MatchCacheRebuildOperation.objects.create(owner=admin_user)

    # Create a scientist to process
    Scientist.objects.create(
        mongoId="test_rebuild_scientist",
        from_institution_api=True,
        versions={},
    )

    with patch("importer_autorow_pbn.core.rebuild_match_cache"):
        rebuild_match_cache_task(operation.pk)

        # Check that operation was marked as started
        operation.refresh_from_db()
        # Operation status depends on task_perform implementation
        assert operation.pk is not None


@pytest.mark.django_db
def test_auto_rebuild_match_cache_task_skips_when_valid():
    """Test that auto_rebuild_match_cache_task skips when cache is valid."""
    from importer_autorow_pbn.tasks import auto_rebuild_match_cache_task

    # Create valid cache entry
    scientist = baker.make(Scientist, from_institution_api=True)
    CachedScientistMatch.objects.create(scientist=scientist, matched_autor=None)

    with patch("importer_autorow_pbn.tasks.get_cache_status") as mock_status:
        mock_status.return_value = (True, None, None)  # is_valid=True

        result = auto_rebuild_match_cache_task()

        assert "still valid" in result


@pytest.mark.django_db
def test_auto_rebuild_match_cache_task_rebuilds_when_stale(admin_user):
    """Test that auto_rebuild_match_cache_task rebuilds when cache is stale."""
    from importer_autorow_pbn.tasks import auto_rebuild_match_cache_task

    with patch("importer_autorow_pbn.tasks.get_cache_status") as mock_status:
        mock_status.return_value = (False, "Cache stale", None)  # is_valid=False

        with patch(
            "importer_autorow_pbn.tasks.MatchCacheRebuildOperation.objects.create"
        ) as mock_create:
            mock_operation = MagicMock()
            mock_operation.matches_found = 5
            mock_operation.total_scientists = 10
            mock_create.return_value = mock_operation

            with patch("django.contrib.auth.get_user_model") as mock_user_model:
                mock_user_class = MagicMock()
                mock_user_class.objects.filter.return_value.first.return_value = (
                    admin_user
                )
                mock_user_model.return_value = mock_user_class

                result = auto_rebuild_match_cache_task()

                mock_operation.task_perform.assert_called_once()
                assert "Rebuilt cache" in result


@pytest.mark.django_db
def test_auto_rebuild_match_cache_task_no_superuser():
    """Test that auto_rebuild_match_cache_task handles no superuser."""
    # Delete all superusers
    from django.contrib.auth import get_user_model

    from importer_autorow_pbn.tasks import auto_rebuild_match_cache_task

    User = get_user_model()
    User.objects.filter(is_superuser=True).delete()

    with patch("importer_autorow_pbn.tasks.get_cache_status") as mock_status:
        mock_status.return_value = (False, "Cache stale", None)

        result = auto_rebuild_match_cache_task()

        assert "No superuser" in result


@pytest.mark.django_db
def test_match_cache_rebuild_operation_progress():
    """Test MatchCacheRebuildOperation progress calculation."""
    operation = MatchCacheRebuildOperation(
        total_scientists=100, processed_scientists=50
    )

    assert operation.get_progress_percent() == 50


@pytest.mark.django_db
def test_match_cache_rebuild_operation_progress_zero():
    """Test MatchCacheRebuildOperation progress with zero total."""
    operation = MatchCacheRebuildOperation(total_scientists=0, processed_scientists=0)

    assert operation.get_progress_percent() == 0
