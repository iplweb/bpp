"""Unit tests for ImportLog model"""

from datetime import timedelta

import pytest
from django.utils import timezone
from model_bakery import baker

from pbn_import.models import ImportLog, ImportSession

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
        assert logs[0] == log2
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
