"""Unit tests for PBN import progress and log views"""

from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from pbn_import.models import ImportLog, ImportSession

# ============================================================================
# PROGRESS VIEW TESTS
# ============================================================================


@pytest.mark.django_db
class TestImportProgressView:
    """Test ImportProgressView"""

    def test_progress_view_requires_permission(self, django_user_model):
        """Test progress view requires permission"""
        client = Client()
        user = baker.make(django_user_model)
        session = baker.make(ImportSession, user=user)
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:progress", args=[session.id]),
        )

        assert response.status_code == 403

    def test_progress_view_returns_session(self, django_user_model):
        """Test progress view returns session data"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
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


# ============================================================================
# LOG STREAM VIEW TESTS
# ============================================================================


@pytest.mark.django_db
class TestImportLogStreamView:
    """Test ImportLogStreamView"""

    def test_log_stream_requires_permission(self, django_user_model):
        """Test log stream requires permission"""
        client = Client()
        user = baker.make(django_user_model)
        session = baker.make(ImportSession, user=user)
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:logs", args=[session.id]),
        )

        assert response.status_code == 403

    def test_log_stream_returns_logs(self, django_user_model):
        """Test log stream returns session logs"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
        session = baker.make(ImportSession, user=user)
        baker.make(ImportLog, session=session)
        baker.make(ImportLog, session=session)
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:logs", args=[session.id]),
        )

        assert response.status_code == 200
        logs = list(response.context.get("logs", []))
        assert len(logs) <= 50

    def test_log_stream_limits_to_50_entries(self, django_user_model):
        """Test log stream returns max 50 entries"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
        session = baker.make(ImportSession, user=user)

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
