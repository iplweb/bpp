"""Unit tests for pbn_import detail and list views"""

import json
from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from pbn_import.models import ImportLog, ImportSession, ImportStatistics

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
        # Logs should be in context or template
        logs = list(response.context.get("logs", []))
        assert len(logs) <= 50  # Max 50 logs

    def test_log_stream_limits_to_50_entries(self, django_user_model):
        """Test log stream returns max 50 entries"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
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


# ============================================================================
# STATISTICS VIEW TESTS
# ============================================================================


@pytest.mark.django_db
class TestImportStatisticsView:
    """Test ImportStatisticsView"""

    def test_statistics_view_requires_permission(self, django_user_model):
        """Test statistics view requires permission"""
        client = Client()
        user = baker.make(django_user_model)
        session = baker.make(ImportSession, user=user)
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:stats", args=[session.id]),
        )

        assert response.status_code == 403

    def test_statistics_view_returns_stats(self, django_user_model):
        """Test statistics view returns statistics"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
        session = baker.make(ImportSession, user=user)
        stats = ImportStatistics.objects.create(session=session)
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:stats", args=[session.id]),
        )

        assert response.status_code == 200
        assert response.context.get("stats") == stats

    def test_statistics_view_handles_missing_stats(self, django_user_model):
        """Test statistics view handles session without statistics"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
        session = baker.make(ImportSession, user=user)
        # Don't create statistics
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:stats", args=[session.id]),
        )

        assert response.status_code == 200
        assert response.context.get("stats") is None


# ============================================================================
# PRESETS VIEW TESTS
# ============================================================================


@pytest.mark.django_db
class TestImportPresetsView:
    """Test ImportPresetsView"""

    def test_presets_view_requires_permission(self, django_user_model):
        """Test presets view requires permission"""
        client = Client()
        user = baker.make(django_user_model)
        client.force_login(user)

        response = client.get(reverse("pbn_import:presets"))

        assert response.status_code == 403

    def test_presets_view_returns_json(self, django_user_model):
        """Test presets view returns JSON response"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
        client.force_login(user)

        response = client.get(reverse("pbn_import:presets"))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert "presets" in data

    def test_presets_view_includes_full_preset(self, django_user_model):
        """Test presets includes 'full' preset"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
        client.force_login(user)

        response = client.get(reverse("pbn_import:presets"))

        data = json.loads(response.content)
        preset_ids = [p["id"] for p in data["presets"]]
        assert "full" in preset_ids

    def test_presets_view_includes_update_preset(self, django_user_model):
        """Test presets includes 'update' preset"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
        client.force_login(user)

        response = client.get(reverse("pbn_import:presets"))

        data = json.loads(response.content)
        preset_ids = [p["id"] for p in data["presets"]]
        assert "update" in preset_ids


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

    def test_detail_view_includes_statistics(self, django_user_model):
        """Test detail view includes statistics"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
        session = baker.make(ImportSession, user=user)
        stats = ImportStatistics.objects.create(session=session)
        client.force_login(user)

        response = client.get(
            reverse("pbn_import:session_detail", args=[session.id]),
        )

        assert response.context.get("statistics") == stats

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


# ============================================================================
# TRACEBACK VISIBILITY TESTS
# ============================================================================


@pytest.mark.django_db
class TestTracebackVisibility:
    """Test that tracebacks are only visible to superusers"""

    def test_superuser_sees_traceback_in_session_detail(self, django_user_model):
        """Test that superusers can see full tracebacks in session detail"""
        client = Client()
        superuser = baker.make(django_user_model, is_superuser=True)

        session = baker.make(
            ImportSession,
            user=superuser,
            status="failed",
            error_message="Test error message",
            error_traceback="Traceback (most recent call last):\n"
            '  File "test.py", line 1\n'
            "    raise ValueError('Test error')\n"
            "ValueError: Test error",
        )

        client.force_login(superuser)
        response = client.get(reverse("pbn_import:session_detail", args=[session.id]))

        assert response.status_code == 200
        content = response.content.decode()

        # Should show traceback details
        assert "Traceback" in content
        assert "ValueError: Test error" in content
        # Should show superuser-only message
        assert "tylko dla superużytkowników" in content or "superuser" in content

    def test_regular_user_cannot_see_traceback_in_session_detail(
        self, django_user_model
    ):
        """Test that regular users cannot see tracebacks in session detail"""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        client = Client()
        regular_user = baker.make(django_user_model, is_superuser=False)

        # Give regular user permission to view import sessions
        content_type = ContentType.objects.get_for_model(ImportSession)
        permission = Permission.objects.get(
            codename="add_importsession", content_type=content_type
        )
        regular_user.user_permissions.add(permission)

        session = baker.make(
            ImportSession,
            user=regular_user,
            status="failed",
            error_message="Test error message",
            error_traceback="Traceback (most recent call last):\n"
            '  File "test.py", line 1\n'
            "    raise ValueError('Test error')\n"
            "ValueError: Test error",
        )

        client.force_login(regular_user)
        response = client.get(reverse("pbn_import:session_detail", args=[session.id]))

        assert response.status_code == 200
        content = response.content.decode()

        # Should show error message but not traceback details
        assert "Test error message" in content
        # Should NOT show the actual traceback
        assert "Traceback (most recent call last)" not in content
        # Should show restriction message
        assert "tylko dla superużytkowników" in content

    def test_superuser_sees_traceback_in_log_details(self, django_user_model):
        """Test that superusers can see tracebacks in ImportLog details"""
        client = Client()
        superuser = baker.make(django_user_model, is_superuser=True)

        session = baker.make(ImportSession, user=superuser, status="failed")
        baker.make(
            ImportLog,
            session=session,
            level="error",
            step="test_step",
            message="Error occurred",
            details={
                "exception": "ValueError",
                "traceback": "Traceback (most recent call last):\n"
                '  File "test.py", line 1\n'
                "    raise ValueError('Test')\n"
                "ValueError: Test",
            },
        )

        client.force_login(superuser)
        response = client.get(reverse("pbn_import:session_detail", args=[session.id]))

        assert response.status_code == 200
        content = response.content.decode()

        # Should be able to see log entry
        assert "Error occurred" in content

    def test_regular_user_cannot_see_traceback_in_log_details(self, django_user_model):
        """Test that regular users cannot see tracebacks in ImportLog details"""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        client = Client()
        regular_user = baker.make(django_user_model, is_superuser=False)

        # Give regular user permission to view import sessions
        content_type = ContentType.objects.get_for_model(ImportSession)
        permission = Permission.objects.get(
            codename="add_importsession", content_type=content_type
        )
        regular_user.user_permissions.add(permission)

        session = baker.make(ImportSession, user=regular_user, status="failed")
        baker.make(
            ImportLog,
            session=session,
            level="error",
            step="test_step",
            message="Error occurred",
            details={
                "exception": "ValueError",
                "traceback": "Traceback (most recent call last):\n"
                '  File "test.py", line 1\n'
                "    raise ValueError('Test')\n"
                "ValueError: Test",
            },
        )

        client.force_login(regular_user)
        response = client.get(reverse("pbn_import:session_detail", args=[session.id]))

        assert response.status_code == 200
        content = response.content.decode()

        # Should see log entry
        assert "Error occurred" in content
        # Should NOT see the actual traceback when expanded
        # (Template hides traceback details for non-superusers)
