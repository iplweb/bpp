"""Tests for error handling in PBN import"""

import traceback
from unittest.mock import patch

import pytest

from pbn_import.models import ImportLog, ImportSession
from pbn_import.utils.base import ImportStepBase


@pytest.mark.django_db
def test_mark_failed_includes_traceback():
    """Test that mark_failed stores traceback"""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(username="testuser")

    session = ImportSession.objects.create(user=user)

    try:
        raise RuntimeError("Test failure")
    except RuntimeError:
        tb = traceback.format_exc()
        session.mark_failed("Test error", tb)

    session.refresh_from_db()
    assert session.status == "failed"
    assert session.error_message == "Test error"
    assert "RuntimeError: Test failure" in session.error_traceback
    assert "Traceback" in session.error_traceback


@pytest.mark.django_db
def test_handle_error_creates_log_with_traceback():
    """Test that handle_error creates ImportLog with traceback"""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(username="testuser")

    session = ImportSession.objects.create(user=user)

    class TestStep(ImportStepBase):
        step_name = "test_step"

        def run(self):
            pass

    step = TestStep(session, client=None)

    try:
        raise ValueError("Test error")
    except ValueError as e:
        step.handle_error(e, "test context")

    # Check ImportLog was created with traceback
    log = ImportLog.objects.filter(session=session, level="error").first()
    assert log is not None
    assert "Test error" in log.message
    assert log.details is not None
    assert "traceback" in log.details
    assert "ValueError: Test error" in log.details["traceback"]


@pytest.mark.django_db
def test_rollbar_called_with_context():
    """Test that rollbar.report_exc_info is called with context"""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(username="testuser")

    session = ImportSession.objects.create(user=user)

    class TestStep(ImportStepBase):
        step_name = "test_step"

        def run(self):
            pass

    step = TestStep(session, client=None)

    with patch("pbn_import.utils.base.rollbar.report_exc_info") as mock_rollbar:
        try:
            raise RuntimeError("Test error")
        except RuntimeError as e:
            step.handle_error(e, "test context")

        assert mock_rollbar.called
        call_args = mock_rollbar.call_args
        assert call_args[1]["extra_data"]["step"] == "test_step"
        assert call_args[1]["extra_data"]["session_id"] == session.id
        assert call_args[1]["extra_data"]["context"] == "test context"


@pytest.mark.django_db
def test_handle_pbn_error_authorization():
    """Test that handle_pbn_error properly handles authorization errors"""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(username="testuser")

    session = ImportSession.objects.create(user=user)

    class TestStep(ImportStepBase):
        step_name = "test_step"

        def run(self):
            pass

    step = TestStep(session, client=None)

    with patch("pbn_import.utils.base.rollbar.report_exc_info") as mock_rollbar:
        with pytest.raises(Exception, match="403 Forbidden"):
            try:
                raise Exception("403 Forbidden")
            except Exception as e:
                step.handle_pbn_error(e, "auth test")

        # Should have reported to Rollbar
        assert mock_rollbar.called
        call_args = mock_rollbar.call_args
        assert call_args[1]["extra_data"]["error_type"] == "authorization"

        # Should have created a critical log entry
        log = ImportLog.objects.filter(session=session, level="critical").first()
        assert log is not None
        assert "Błąd autoryzacji PBN" in log.message
        assert log.details is not None
        assert "traceback" in log.details


@pytest.mark.django_db
def test_handle_pbn_error_non_auth():
    """Test that handle_pbn_error delegates to handle_error for non-auth errors"""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(username="testuser")

    session = ImportSession.objects.create(user=user)

    class TestStep(ImportStepBase):
        step_name = "test_step"

        def run(self):
            pass

    step = TestStep(session, client=None)

    with patch("pbn_import.utils.base.rollbar.report_exc_info") as mock_rollbar:
        try:
            raise ValueError("Regular error")
        except ValueError as e:
            step.handle_pbn_error(e, "pbn test")

        # Should have reported to Rollbar via handle_error
        assert mock_rollbar.called

        # Should have created an error log entry (not critical)
        log = ImportLog.objects.filter(session=session, level="error").first()
        assert log is not None
        assert "Regular error" in log.message
