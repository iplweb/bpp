"""Unit tests for pbn_import models"""

from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone
from model_bakery import baker

from pbn_import.models import (
    ImportLog,
    ImportSession,
    ImportStatistics,
    ImportStep,
)

# ============================================================================
# IMPORT SESSION MODEL TESTS
# ============================================================================


@pytest.mark.django_db
class TestImportSessionModel:
    """Test ImportSession model methods and properties"""

    def test_import_session_creation_defaults(self, django_user_model):
        """Test ImportSession is created with correct defaults"""
        user = baker.make(django_user_model)
        session = ImportSession.objects.create(user=user)

        assert session.user == user
        assert session.status == "pending"
        assert session.current_step_progress == 0
        assert session.total_steps == 0
        assert session.completed_steps == 0
        assert session.task_id is None
        assert session.error_message == ""
        assert session.completed_at is None

    def test_import_session_str_representation(self, django_user_model):
        """Test ImportSession __str__ method"""
        user = baker.make(django_user_model, username="testuser")
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
