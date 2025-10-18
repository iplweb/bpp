"""Unit tests for pbn_import models and views"""

import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from bpp.models import Uczelnia
from pbn_import.models import (
    ImportLog,
    ImportSession,
    ImportStatistics,
    ImportStep,
)

User = get_user_model()


# ============================================================================
# IMPORT SESSION MODEL TESTS
# ============================================================================


@pytest.mark.django_db
class TestImportSessionModel:
    """Test ImportSession model methods and properties"""

    def test_import_session_creation_defaults(self):
        """Test ImportSession is created with correct defaults"""
        user = baker.make(User)
        session = ImportSession.objects.create(user=user)

        assert session.user == user
        assert session.status == "pending"
        assert session.current_step_progress == 0
        assert session.total_steps == 0
        assert session.completed_steps == 0
        assert session.task_id is None
        assert session.error_message == ""
        assert session.completed_at is None

    def test_import_session_str_representation(self):
        """Test ImportSession __str__ method"""
        user = baker.make(User, username="testuser")
        session = baker.make(
            ImportSession,
            user=user,
            status="running",
        )

        str_repr = str(session)
        assert "testuser" in str_repr
        assert "W trakcie" in str_repr

    def test_import_session_mark_completed(self):
        """Test mark_completed() sets correct status and timestamp"""
        session = baker.make(ImportSession, status="running", completed_at=None)

        before_time = timezone.now()
        session.mark_completed()
        after_time = timezone.now()

        session.refresh_from_db()
        assert session.status == "completed"
        assert session.completed_at is not None
        assert before_time <= session.completed_at <= after_time

    def test_import_session_mark_failed_with_message(self):
        """Test mark_failed() sets error status and details"""
        session = baker.make(ImportSession, status="running", completed_at=None)
        error_msg = "Test error message"
        error_trace = "Traceback: test"

        before_time = timezone.now()
        session.mark_failed(error_msg, error_trace)
        after_time = timezone.now()

        session.refresh_from_db()
        assert session.status == "failed"
        assert session.error_message == error_msg
        assert session.error_traceback == error_trace
        assert session.completed_at is not None
        assert before_time <= session.completed_at <= after_time

    def test_import_session_update_progress(self):
        """Test update_progress() updates step and progress fields"""
        session = baker.make(
            ImportSession,
            current_step="",
            current_step_progress=0,
            completed_steps=0,
        )

        session.update_progress("Importing authors", 45, step_number=2)
        session.refresh_from_db()

        assert session.current_step == "Importing authors"
        assert session.current_step_progress == 45
        assert session.completed_steps == 2

    def test_import_session_update_progress_without_step_number(self):
        """Test update_progress() works without step_number parameter"""
        session = baker.make(ImportSession, completed_steps=1)

        session.update_progress("Next step", 30)
        session.refresh_from_db()

        assert session.current_step == "Next step"
        assert session.current_step_progress == 30
        assert session.completed_steps == 1  # unchanged

    def test_import_session_overall_progress_zero_steps(self):
        """Test overall_progress returns 0 when total_steps is 0"""
        session = baker.make(
            ImportSession,
            total_steps=0,
            completed_steps=0,
            current_step_progress=50,
        )

        assert session.overall_progress == 0

    def test_import_session_overall_progress_calculation(self):
        """Test overall_progress calculation with multiple steps"""
        session = baker.make(
            ImportSession,
            total_steps=10,
            completed_steps=5,
            current_step_progress=50,
        )

        # (5 / 10) * 100 + (50 / 10) = 50 + 5 = 55
        assert session.overall_progress == 55

    def test_import_session_overall_progress_capped_at_100(self):
        """Test overall_progress is capped at 100%"""
        session = baker.make(
            ImportSession,
            total_steps=10,
            completed_steps=9,
            current_step_progress=200,  # impossible but let's test edge case
        )

        # (9 / 10) * 100 + (200 / 10) = 90 + 20 = 110 -> capped to 100
        assert session.overall_progress == 100

    def test_import_session_duration_with_completed_at(self):
        """Test duration property with completed_at set"""
        now = timezone.now()
        session = baker.make(
            ImportSession,
            started_at=now,
            completed_at=now + timedelta(hours=1),
        )

        assert session.duration == timedelta(hours=1)

    def test_import_session_duration_without_completed_at(self):
        """Test duration property calculates from started_at to now"""
        now = timezone.now()
        session = baker.make(
            ImportSession,
            started_at=now,
            completed_at=None,
        )

        duration = session.duration
        assert duration is not None
        assert duration.total_seconds() >= 0
        assert duration.total_seconds() < 2  # Should be very small


# ============================================================================
# IMPORT LOG MODEL TESTS
# ============================================================================


@pytest.mark.django_db
class TestImportLogModel:
    """Test ImportLog model"""

    def test_import_log_creation_defaults(self):
        """Test ImportLog is created with correct defaults"""
        session = baker.make(ImportSession)
        log = ImportLog.objects.create(
            session=session,
            step="test_step",
            message="test message",
        )

        assert log.session == session
        assert log.step == "test_step"
        assert log.message == "test message"
        assert log.level == "info"
        assert log.details is None

    def test_import_log_creation_with_all_fields(self):
        """Test ImportLog with all fields set"""
        session = baker.make(ImportSession)
        details = {"count": 10, "type": "author"}

        log = ImportLog.objects.create(
            session=session,
            level="success",
            step="author_import",
            message="Authors imported successfully",
            details=details,
        )

        assert log.level == "success"
        assert log.details == details

    def test_import_log_str_representation(self):
        """Test ImportLog __str__ method"""
        session = baker.make(ImportSession)
        log = baker.make(
            ImportLog,
            session=session,
            level="warning",
            message="This is a very long warning message that should be truncated",
        )

        str_repr = str(log)
        assert "warning" in str_repr.lower()

    def test_import_log_ordering(self):
        """Test ImportLog objects are ordered by timestamp descending"""
        session = baker.make(ImportSession)
        now = timezone.now()

        log1 = ImportLog.objects.create(
            session=session,
            step="step1",
            message="First",
            timestamp=now - timedelta(seconds=10),
        )
        log2 = ImportLog.objects.create(
            session=session,
            step="step2",
            message="Second",
            timestamp=now,
        )

        logs = list(ImportLog.objects.filter(session=session))
        assert logs[0] == log2  # Newest first
        assert logs[1] == log1

    def test_import_log_level_choices(self):
        """Test all valid log levels can be created"""
        session = baker.make(ImportSession)
        levels = ["debug", "info", "warning", "error", "success", "critical"]

        for level in levels:
            log = ImportLog.objects.create(
                session=session,
                step="test",
                message=f"Test {level}",
                level=level,
            )
            assert log.level == level


# ============================================================================
# IMPORT STEP MODEL TESTS
# ============================================================================


@pytest.mark.django_db
class TestImportStepModel:
    """Test ImportStep model"""

    def test_import_step_creation(self):
        """Test ImportStep creation with required fields"""
        step = ImportStep.objects.create(
            name="import_authors",
            display_name="Import Authors",
            order=1,
        )

        assert step.name == "import_authors"
        assert step.display_name == "Import Authors"
        assert step.order == 1
        assert step.is_optional is False
        assert step.estimated_duration == 60
        assert step.icon_class == "fi-download"

    def test_import_step_with_optional(self):
        """Test ImportStep with optional field"""
        step = baker.make(
            ImportStep,
            name="optional_step",
            is_optional=True,
        )

        assert step.is_optional is True

    def test_import_step_ordering(self):
        """Test ImportStep objects are ordered by order field"""
        step1 = ImportStep.objects.create(
            name="first",
            display_name="First",
            order=1,
        )
        step2 = ImportStep.objects.create(
            name="second",
            display_name="Second",
            order=2,
        )
        step3 = ImportStep.objects.create(
            name="third",
            display_name="Third",
            order=3,
        )

        steps = list(ImportStep.objects.all())
        assert steps[0] == step1
        assert steps[1] == step2
        assert steps[2] == step3

    def test_import_step_str_representation(self):
        """Test ImportStep __str__ returns display_name"""
        step = baker.make(
            ImportStep,
            display_name="Import Publications",
        )

        assert str(step) == "Import Publications"

    def test_import_step_name_unique(self):
        """Test step name must be unique"""
        ImportStep.objects.create(
            name="unique_step",
            display_name="Display",
            order=1,
        )

        with pytest.raises(IntegrityError):
            ImportStep.objects.create(
                name="unique_step",
                display_name="Different Display",
                order=2,
            )


# ============================================================================
# IMPORT STATISTICS MODEL TESTS
# ============================================================================


@pytest.mark.django_db
class TestImportStatisticsModel:
    """Test ImportStatistics model"""

    def test_import_statistics_creation_defaults(self):
        """Test ImportStatistics is created with all counters at 0"""
        session = baker.make(ImportSession)
        stats = ImportStatistics.objects.create(session=session)

        assert stats.session == session
        assert stats.institutions_imported == 0
        assert stats.authors_imported == 0
        assert stats.publications_imported == 0
        assert stats.journals_imported == 0
        assert stats.publishers_imported == 0
        assert stats.conferences_imported == 0
        assert stats.statements_imported == 0
        assert stats.institutions_failed == 0
        assert stats.authors_failed == 0
        assert stats.publications_failed == 0
        assert stats.total_api_calls == 0
        assert stats.total_api_time == 0.0

    def test_import_statistics_one_to_one_relationship(self):
        """Test ImportStatistics has one-to-one relationship with session"""
        session = baker.make(ImportSession)
        stats = ImportStatistics.objects.create(session=session)

        assert session.statistics == stats

    def test_import_statistics_str_representation(self):
        """Test ImportStatistics __str__ method"""
        session = baker.make(ImportSession)
        stats = ImportStatistics.objects.create(session=session)

        assert "Statystyki dla" in str(stats)

    def test_import_statistics_calculate_coffee_breaks_zero_duration(self):
        """Test coffee breaks calculation with no duration"""
        session = baker.make(
            ImportSession,
            started_at=timezone.now(),
            completed_at=None,
        )
        stats = ImportStatistics.objects.create(session=session)

        # Session is still running, duration should be minimal
        result = stats.calculate_coffee_breaks()
        assert result >= 0

    def test_import_statistics_calculate_coffee_breaks_30_minutes(self):
        """Test coffee breaks calculation (1 break per 30 minutes)"""
        now = timezone.now()
        session = baker.make(
            ImportSession,
            started_at=now,
            completed_at=now + timedelta(minutes=30),
        )
        stats = ImportStatistics.objects.create(session=session)

        result = stats.calculate_coffee_breaks()
        assert result == 1

    def test_import_statistics_calculate_coffee_breaks_90_minutes(self):
        """Test coffee breaks calculation with 90 minutes"""
        now = timezone.now()
        session = baker.make(
            ImportSession,
            started_at=now,
            completed_at=now + timedelta(minutes=90),
        )
        stats = ImportStatistics.objects.create(session=session)

        result = stats.calculate_coffee_breaks()
        assert result == 3  # 90 / 30 = 3

    def test_import_statistics_increment_counters(self):
        """Test incrementing various counters"""
        session = baker.make(ImportSession)
        stats = ImportStatistics.objects.create(session=session)

        stats.authors_imported = 50
        stats.publications_imported = 100
        stats.authors_failed = 5
        stats.total_api_calls = 200
        stats.total_api_time = 45.5
        stats.save()

        stats.refresh_from_db()
        assert stats.authors_imported == 50
        assert stats.publications_imported == 100
        assert stats.authors_failed == 5
        assert stats.total_api_calls == 200
        assert stats.total_api_time == 45.5


# ============================================================================
# VIEW TESTS
# ============================================================================


@pytest.mark.django_db
class TestImportDashboardView:
    """Test ImportDashboardView"""

    def test_dashboard_requires_login(self):
        """Test dashboard requires authentication"""
        client = Client()
        response = client.get(reverse("pbn_import:dashboard"))

        assert response.status_code == 302  # Redirect to login

    def test_dashboard_requires_permission(self):
        """Test dashboard requires pbn_import permission"""
        client = Client()
        user = baker.make(User)
        client.force_login(user)

        response = client.get(reverse("pbn_import:dashboard"))

        assert response.status_code == 403  # Forbidden

    def test_dashboard_accessible_with_superuser(self):
        """Test dashboard is accessible to superuser"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        client.force_login(user)
        baker.make(Uczelnia, pbn_integracja=True)

        response = client.get(reverse("pbn_import:dashboard"))

        assert response.status_code == 200

    def test_dashboard_accessible_with_permission(self):
        """Test dashboard accessible with add_importsession permission"""
        from django.contrib.contenttypes.models import ContentType

        client = Client()
        user = baker.make(User)

        # Get or create the permission with correct content type
        content_type = ContentType.objects.get_for_model(ImportSession)
        from django.contrib.auth.models import Permission

        perm, _ = Permission.objects.get_or_create(
            codename="add_importsession",
            content_type=content_type,
            defaults={"name": "Can add import session"},
        )
        user.user_permissions.add(perm)

        client.force_login(user)
        baker.make(Uczelnia, pbn_integracja=True)

        response = client.get(reverse("pbn_import:dashboard"))

        assert response.status_code == 200

    def test_dashboard_accessible_with_group(self):
        """Test dashboard accessible with 'wprowadzanie danych' group"""
        client = Client()
        user = baker.make(User)
        group, _ = Group.objects.get_or_create(name="wprowadzanie danych")
        user.groups.add(group)
        client.force_login(user)
        baker.make(Uczelnia, pbn_integracja=True)

        response = client.get(reverse("pbn_import:dashboard"))

        assert response.status_code == 200

    def test_dashboard_context_recent_sessions(self):
        """Test dashboard context includes recent sessions"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        client.force_login(user)
        baker.make(Uczelnia, pbn_integracja=True)

        session1 = baker.make(ImportSession, user=user)
        session2 = baker.make(ImportSession, user=user)
        ImportStatistics.objects.create(session=session1)
        ImportStatistics.objects.create(session=session2)

        response = client.get(reverse("pbn_import:dashboard"))

        assert response.status_code == 200
        assert "recent_sessions" in response.context
        assert len(response.context["recent_sessions"]) == 2

    def test_dashboard_context_active_session(self):
        """Test dashboard context includes active session if running"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        client.force_login(user)
        baker.make(Uczelnia, pbn_integracja=True)

        running_session = baker.make(
            ImportSession,
            user=user,
            status="running",
        )
        completed_session = baker.make(
            ImportSession,
            user=user,
            status="completed",
        )
        ImportStatistics.objects.create(session=running_session)
        ImportStatistics.objects.create(session=completed_session)

        response = client.get(reverse("pbn_import:dashboard"))

        assert response.context["active_session"] == running_session

    def test_dashboard_shows_only_user_sessions(self):
        """Test dashboard only shows sessions for logged-in user"""
        client = Client()
        user1 = baker.make(User, is_superuser=True)
        user2 = baker.make(User)
        client.force_login(user1)
        baker.make(Uczelnia, pbn_integracja=True)

        session1 = baker.make(ImportSession, user=user1)
        session2 = baker.make(ImportSession, user=user2)
        ImportStatistics.objects.create(session=session1)
        ImportStatistics.objects.create(session=session2)

        response = client.get(reverse("pbn_import:dashboard"))

        assert session1 in response.context["recent_sessions"]
        assert session2 not in response.context["recent_sessions"]


@pytest.mark.django_db
class TestStartImportView:
    """Test StartImportView"""

    def test_start_import_requires_permission(self):
        """Test start import requires permission"""
        client = Client()
        user = baker.make(User)
        client.force_login(user)

        response = client.post(reverse("pbn_import:start"))

        assert response.status_code == 403

    def test_start_import_creates_session(self):
        """Test start import creates ImportSession"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        baker.make(Uczelnia, pbn_integracja=True)
        client.force_login(user)

        with (
            patch("pbn_import.tasks.run_pbn_import") as mock_task,
            patch("pbn_import.views.get_channel_layer"),
            patch("pbn_import.views.async_to_sync"),
        ):
            mock_task.delay.return_value = MagicMock(id="task-123")

            client.post(
                reverse("pbn_import:start"),
                {
                    "initial": "on",
                    "zrodla": "on",
                    "wydawcy": "on",
                },
            )

        session = ImportSession.objects.get(user=user)
        assert session.status == "pending"
        assert session.user == user

    def test_start_import_creates_statistics(self):
        """Test start import creates ImportStatistics"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        baker.make(Uczelnia, pbn_integracja=True)
        client.force_login(user)

        with (
            patch("pbn_import.tasks.run_pbn_import") as mock_task,
            patch("pbn_import.views.get_channel_layer"),
            patch("pbn_import.views.async_to_sync"),
        ):
            mock_task.delay.return_value = MagicMock(id="task-123")

            client.post(reverse("pbn_import:start"), {})

        session = ImportSession.objects.get(user=user)
        assert ImportStatistics.objects.filter(session=session).exists()

    def test_start_import_stores_config(self):
        """Test start import stores configuration from POST data"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        baker.make(Uczelnia, pbn_integracja=True)
        client.force_login(user)

        with (
            patch("pbn_import.tasks.run_pbn_import") as mock_task,
            patch("pbn_import.views.get_channel_layer"),
            patch("pbn_import.views.async_to_sync"),
        ):
            mock_task.delay.return_value = MagicMock(id="task-123")

            client.post(
                reverse("pbn_import:start"),
                {
                    "initial": "on",
                    "zrodla": "on",
                    "delete_existing": "on",
                    "wydzial_domyslny": "IT Department",
                },
            )

        session = ImportSession.objects.get(user=user)
        assert session.config["delete_existing"] is True
        assert session.config["wydzial_domyslny"] == "IT Department"

    def test_start_import_redirects_to_dashboard(self):
        """Test start import redirects to dashboard after creation"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        baker.make(Uczelnia, pbn_integracja=True)
        client.force_login(user)

        with (
            patch("pbn_import.tasks.run_pbn_import") as mock_task,
            patch("pbn_import.views.get_channel_layer"),
            patch("pbn_import.views.async_to_sync"),
        ):
            mock_task.delay.return_value = MagicMock(id="task-123")

            response = client.post(
                reverse("pbn_import:start"),
                {},
                follow=False,
            )

        assert response.status_code in [302, 303, 307]  # Redirect codes


@pytest.mark.django_db
class TestCancelImportView:
    """Test CancelImportView"""

    def test_cancel_import_requires_permission(self):
        """Test cancel import requires permission"""
        client = Client()
        user = baker.make(User)
        session = baker.make(ImportSession, user=user)
        client.force_login(user)

        response = client.post(reverse("pbn_import:cancel", args=[session.id]))

        assert response.status_code == 403

    def test_cancel_running_import(self):
        """Test cancelling a running import session"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        session = baker.make(
            ImportSession,
            user=user,
            status="running",
            task_id="task-123",
        )
        client.force_login(user)

        with patch("celery.current_app"), patch("pbn_import.views.get_channel_layer"):
            client.post(reverse("pbn_import:cancel", args=[session.id]))

        session.refresh_from_db()
        assert session.status == "cancelled"
        assert session.completed_at is not None

    def test_cancel_pending_import(self):
        """Test cancelling a pending import session"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        session = baker.make(
            ImportSession,
            user=user,
            status="pending",
        )
        client.force_login(user)

        client.post(reverse("pbn_import:cancel", args=[session.id]))

        session.refresh_from_db()
        assert session.status == "cancelled"

    def test_cannot_cancel_completed_import(self):
        """Test cannot cancel already completed import"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        session = baker.make(
            ImportSession,
            user=user,
            status="completed",
        )
        client.force_login(user)

        client.post(reverse("pbn_import:cancel", args=[session.id]))

        session.refresh_from_db()
        assert session.status == "completed"  # Unchanged

    def test_cancel_creates_log_entry(self):
        """Test cancellation creates log entry"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        session = baker.make(
            ImportSession,
            user=user,
            status="running",
        )
        client.force_login(user)

        with patch("celery.current_app"), patch("pbn_import.views.get_channel_layer"):
            client.post(reverse("pbn_import:cancel", args=[session.id]))

        log = ImportLog.objects.filter(session=session).last()
        assert log is not None
        assert "anulowany" in log.message.lower()

    def test_cancel_only_own_sessions(self):
        """Test user can only cancel their own sessions"""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        client = Client()
        user1 = baker.make(User, is_superuser=False)
        user2 = baker.make(User, is_superuser=False)
        session = baker.make(ImportSession, user=user2, status="running")

        content_type = ContentType.objects.get_for_model(ImportSession)
        perm, _ = Permission.objects.get_or_create(
            codename="add_importsession",
            content_type=content_type,
            defaults={"name": "Can add import session"},
        )
        user1.user_permissions.add(perm)
        client.force_login(user1)

        response = client.post(reverse("pbn_import:cancel", args=[session.id]))

        assert response.status_code == 404


@pytest.mark.django_db
class TestImportProgressView:
    """Test ImportProgressView"""

    def test_progress_view_requires_permission(self):
        """Test progress view requires permission"""
        client = Client()
        user = baker.make(User)
        session = baker.make(ImportSession, user=user)
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:progress", args=[session.id]),
        )

        assert response.status_code == 403

    def test_progress_view_returns_session(self):
        """Test progress view returns session data"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        session = baker.make(
            ImportSession,
            user=user,
            total_steps=10,
            completed_steps=5,
            current_step_progress=50,
        )
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:progress", args=[session.id]),
        )

        assert response.status_code == 200
        assert response.context["session"] == session


@pytest.mark.django_db
class TestImportLogStreamView:
    """Test ImportLogStreamView"""

    def test_log_stream_requires_permission(self):
        """Test log stream requires permission"""
        client = Client()
        user = baker.make(User)
        session = baker.make(ImportSession, user=user)
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:logs", args=[session.id]),
        )

        assert response.status_code == 403

    def test_log_stream_returns_logs(self):
        """Test log stream returns session logs"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        session = baker.make(ImportSession, user=user)
        baker.make(ImportLog, session=session)
        baker.make(ImportLog, session=session)
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:logs", args=[session.id]),
        )

        assert response.status_code == 200
        # Logs should be in context or template
        logs = list(response.context.get("logs", []))
        assert len(logs) <= 50  # Max 50 logs

    def test_log_stream_limits_to_50_entries(self):
        """Test log stream returns max 50 entries"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        session = baker.make(ImportSession, user=user)

        # Create 100 logs
        for i in range(100):
            baker.make(
                ImportLog,
                session=session,
                timestamp=timezone.now() - timedelta(seconds=i),
            )

        client.force_login(user)
        response = client.get(
            reverse("pbn_import:logs", args=[session.id]),
        )

        logs = list(response.context.get("logs", []))
        assert len(logs) <= 50


@pytest.mark.django_db
class TestImportStatisticsView:
    """Test ImportStatisticsView"""

    def test_statistics_view_requires_permission(self):
        """Test statistics view requires permission"""
        client = Client()
        user = baker.make(User)
        session = baker.make(ImportSession, user=user)
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:stats", args=[session.id]),
        )

        assert response.status_code == 403

    def test_statistics_view_returns_stats(self):
        """Test statistics view returns statistics"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        session = baker.make(ImportSession, user=user)
        stats = ImportStatistics.objects.create(session=session)
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:stats", args=[session.id]),
        )

        assert response.status_code == 200
        assert response.context.get("stats") == stats

    def test_statistics_view_handles_missing_stats(self):
        """Test statistics view handles session without statistics"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        session = baker.make(ImportSession, user=user)
        # Don't create statistics
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:stats", args=[session.id]),
        )

        assert response.status_code == 200
        assert response.context.get("stats") is None


@pytest.mark.django_db
class TestImportPresetsView:
    """Test ImportPresetsView"""

    def test_presets_view_requires_permission(self):
        """Test presets view requires permission"""
        client = Client()
        user = baker.make(User)
        client.force_login(user)

        response = client.get(reverse("pbn_import:presets"))

        assert response.status_code == 403

    def test_presets_view_returns_json(self):
        """Test presets view returns JSON response"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        client.force_login(user)

        response = client.get(reverse("pbn_import:presets"))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert "presets" in data

    def test_presets_view_includes_full_preset(self):
        """Test presets includes 'full' preset"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        client.force_login(user)

        response = client.get(reverse("pbn_import:presets"))

        data = json.loads(response.content)
        preset_ids = [p["id"] for p in data["presets"]]
        assert "full" in preset_ids

    def test_presets_view_includes_update_preset(self):
        """Test presets includes 'update' preset"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        client.force_login(user)

        response = client.get(reverse("pbn_import:presets"))

        data = json.loads(response.content)
        preset_ids = [p["id"] for p in data["presets"]]
        assert "update" in preset_ids


@pytest.mark.django_db
class TestImportSessionDetailView:
    """Test ImportSessionDetailView"""

    def test_detail_view_requires_permission(self):
        """Test detail view requires permission"""
        client = Client()
        user = baker.make(User)
        session = baker.make(ImportSession, user=user)
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:session_detail", args=[session.id]),
        )

        assert response.status_code == 403

    def test_detail_view_shows_user_session(self):
        """Test detail view shows user's own session"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        session = baker.make(ImportSession, user=user)
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:session_detail", args=[session.id]),
        )

        assert response.status_code == 200
        assert response.context["session"] == session

    def test_detail_view_shows_only_user_sessions(self):
        """Test non-superuser can only see own sessions"""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        client = Client()
        user1 = baker.make(User)
        user2 = baker.make(User)
        session = baker.make(ImportSession, user=user2)

        content_type = ContentType.objects.get_for_model(ImportSession)
        perm, _ = Permission.objects.get_or_create(
            codename="add_importsession",
            content_type=content_type,
            defaults={"name": "Can add import session"},
        )
        user1.user_permissions.add(perm)
        client.force_login(user1)

        response = client.get(
            reverse("pbn_import:session_detail", args=[session.id]),
        )

        assert response.status_code == 404

    def test_detail_view_superuser_sees_all_sessions(self):
        """Test superuser can see any session"""
        client = Client()
        superuser = baker.make(User, is_superuser=True)
        other_user = baker.make(User)
        session = baker.make(ImportSession, user=other_user)
        client.force_login(superuser)

        response = client.get(
            reverse("pbn_import:session_detail", args=[session.id]),
        )

        assert response.status_code == 200

    def test_detail_view_includes_logs(self):
        """Test detail view includes session logs"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        session = baker.make(ImportSession, user=user)
        log1 = baker.make(ImportLog, session=session)
        log2 = baker.make(ImportLog, session=session)
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:session_detail", args=[session.id]),
        )

        logs = list(response.context.get("logs", []))
        assert log1 in logs
        assert log2 in logs

    def test_detail_view_includes_error_logs(self):
        """Test detail view includes only error logs in error_logs"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        session = baker.make(ImportSession, user=user)
        error_log = baker.make(ImportLog, session=session, level="error")
        warning_log = baker.make(ImportLog, session=session, level="warning")
        info_log = baker.make(ImportLog, session=session, level="info")
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:session_detail", args=[session.id]),
        )

        error_logs = list(response.context.get("error_logs", []))
        assert error_log in error_logs
        assert warning_log in error_logs
        assert info_log not in error_logs

    def test_detail_view_includes_statistics(self):
        """Test detail view includes statistics"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        session = baker.make(ImportSession, user=user)
        stats = ImportStatistics.objects.create(session=session)
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:session_detail", args=[session.id]),
        )

        assert response.context.get("statistics") == stats

    def test_detail_view_calculates_duration(self):
        """Test detail view calculates session duration"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        now = timezone.now()
        session = baker.make(
            ImportSession,
            user=user,
            started_at=now,
            completed_at=now + timedelta(hours=1),
        )
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:session_detail", args=[session.id]),
        )

        duration = response.context.get("duration")
        assert duration == timedelta(hours=1)


@pytest.mark.django_db
class TestActiveSessionsView:
    """Test ActiveSessionsView"""

    def test_active_sessions_requires_permission(self):
        """Test active sessions view requires permission"""
        client = Client()
        user = baker.make(User)
        client.force_login(user)

        response = client.get(reverse("pbn_import:active_sessions"))

        assert response.status_code == 403

    def test_active_sessions_returns_running_sessions(self):
        """Test active sessions returns only running/paused sessions"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        running = baker.make(ImportSession, status="running")
        paused = baker.make(ImportSession, status="paused")
        completed = baker.make(ImportSession, status="completed")
        client.force_login(user)

        response = client.get(reverse("pbn_import:active_sessions"))

        sessions = list(response.context.get("sessions", []))
        assert running in sessions
        assert paused in sessions
        assert completed not in sessions

    def test_active_sessions_ordered_by_date(self):
        """Test active sessions are ordered by started_at descending"""
        client = Client()
        user = baker.make(User, is_superuser=True)
        now = timezone.now()

        old_session = baker.make(
            ImportSession,
            status="running",
            started_at=now - timedelta(hours=1),
        )
        new_session = baker.make(
            ImportSession,
            status="running",
            started_at=now,
        )
        client.force_login(user)

        response = client.get(reverse("pbn_import:active_sessions"))

        sessions = list(response.context.get("sessions", []))
        assert sessions[0] == new_session
        assert sessions[1] == old_session
