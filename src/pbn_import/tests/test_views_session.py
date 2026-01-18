"""Unit tests for PBN import session detail and active sessions views"""

from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from pbn_import.models import ImportLog, ImportSession

# ============================================================================
# SESSION DETAIL VIEW TESTS
# ============================================================================


@pytest.mark.django_db
class TestImportSessionDetailView:
    """Test ImportSessionDetailView"""

    def test_detail_view_requires_permission(self, django_user_model):
        """Test detail view requires permission"""
        client = Client()
        user = baker.make(django_user_model)
        session = baker.make(ImportSession, user=user)
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:session_detail", args=[session.id]),
        )

        assert response.status_code == 403

    def test_detail_view_shows_user_session(self, django_user_model):
        """Test detail view shows user's own session"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
        session = baker.make(ImportSession, user=user)
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:session_detail", args=[session.id]),
        )

        assert response.status_code == 200
        assert response.context["session"] == session

    def test_detail_view_shows_only_user_sessions(self, django_user_model):
        """Test non-superuser can only see own sessions"""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        client = Client()
        user1 = baker.make(django_user_model)
        user2 = baker.make(django_user_model)
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

    def test_detail_view_superuser_sees_all_sessions(self, django_user_model):
        """Test superuser can see any session"""
        client = Client()
        superuser = baker.make(django_user_model, is_superuser=True)
        other_user = baker.make(django_user_model)
        session = baker.make(ImportSession, user=other_user)
        client.force_login(superuser)

        response = client.get(
            reverse("pbn_import:session_detail", args=[session.id]),
        )

        assert response.status_code == 200

    def test_detail_view_includes_logs(self, django_user_model):
        """Test detail view includes session logs"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
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

    def test_detail_view_includes_error_logs(self, django_user_model):
        """Test detail view includes only error logs in error_logs"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
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

    def test_detail_view_calculates_duration(self, django_user_model):
        """Test detail view calculates session duration"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
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


# ============================================================================
# ACTIVE SESSIONS VIEW TESTS
# ============================================================================


@pytest.mark.django_db
class TestActiveSessionsView:
    """Test ActiveSessionsView"""

    def test_active_sessions_requires_permission(self, django_user_model):
        """Test active sessions view requires permission"""
        client = Client()
        user = baker.make(django_user_model)
        client.force_login(user)

        response = client.get(reverse("pbn_import:active_sessions"))

        assert response.status_code == 403

    def test_active_sessions_returns_running_sessions(self, django_user_model):
        """Test active sessions returns only running/paused sessions"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
        running = baker.make(ImportSession, status="running")
        paused = baker.make(ImportSession, status="paused")
        completed = baker.make(ImportSession, status="completed")
        client.force_login(user)

        response = client.get(reverse("pbn_import:active_sessions"))

        sessions = list(response.context.get("sessions", []))
        assert running in sessions
        assert paused in sessions
        assert completed not in sessions

    def test_active_sessions_ordered_by_date(self, django_user_model):
        """Test active sessions are ordered by started_at descending"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
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
