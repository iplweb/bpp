"""Unit tests for ImportStatistics model"""

from datetime import timedelta

import pytest
from django.utils import timezone
from model_bakery import baker

from pbn_import.models import ImportSession, ImportStatistics

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
        assert result == 3

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
