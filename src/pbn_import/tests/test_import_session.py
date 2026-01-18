"""Unit tests for ImportSession model"""

from datetime import timedelta

import pytest
from django.utils import timezone
from model_bakery import baker

from pbn_import.models import ImportSession

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
        assert session.task_id == ""
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
        assert session.completed_steps == 1

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

        assert session.overall_progress == 55

    def test_import_session_overall_progress_capped_at_100(self):
        """Test overall_progress is capped at 100%"""
        session = baker.make(
            ImportSession,
            total_steps=10,
            completed_steps=9,
            current_step_progress=200,
        )

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
        assert duration.total_seconds() < 2
