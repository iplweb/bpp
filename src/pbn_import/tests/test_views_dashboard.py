"""Unit tests for pbn_import dashboard and start views"""

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse
from model_bakery import baker

from bpp.models import Uczelnia
from pbn_import.models import ImportSession

# ============================================================================
# DASHBOARD VIEW TESTS
# ============================================================================


@pytest.mark.django_db
class TestImportDashboardView:
    """Test ImportDashboardView"""

    def test_dashboard_requires_login(self):
        """Test dashboard requires authentication"""
        client = Client()
        response = client.get(reverse("pbn_import:dashboard"))

        assert response.status_code == 302  # Redirect to login

    def test_dashboard_requires_permission(self, django_user_model):
        """Test dashboard requires pbn_import permission"""
        client = Client()
        user = baker.make(django_user_model)
        client.force_login(user)

        response = client.get(reverse("pbn_import:dashboard"))

        assert response.status_code == 403  # Forbidden

    def test_dashboard_accessible_with_superuser(self, django_user_model):
        """Test dashboard is accessible to superuser"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
        client.force_login(user)
        baker.make(Uczelnia, pbn_integracja=True)

        response = client.get(reverse("pbn_import:dashboard"))

        assert response.status_code == 200

    def test_dashboard_accessible_with_permission(self, django_user_model):
        """Test dashboard accessible with add_importsession permission"""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        client = Client()
        user = baker.make(django_user_model)

        # Get or create the permission with correct content type
        content_type = ContentType.objects.get_for_model(ImportSession)
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

    def test_dashboard_accessible_with_group(self, django_user_model):
        """Test dashboard accessible with 'wprowadzanie danych' group"""
        client = Client()
        user = baker.make(django_user_model)
        group, _ = Group.objects.get_or_create(name="wprowadzanie danych")
        user.groups.add(group)
        client.force_login(user)
        baker.make(Uczelnia, pbn_integracja=True)

        response = client.get(reverse("pbn_import:dashboard"))

        assert response.status_code == 200

    def test_dashboard_context_recent_sessions(self, django_user_model):
        """Test dashboard context includes recent sessions"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
        client.force_login(user)
        baker.make(Uczelnia, pbn_integracja=True)

        baker.make(ImportSession, user=user)
        baker.make(ImportSession, user=user)

        response = client.get(reverse("pbn_import:dashboard"))

        assert response.status_code == 200
        assert "recent_sessions" in response.context
        assert len(response.context["recent_sessions"]) == 2

    def test_dashboard_context_active_session(self, django_user_model):
        """Test dashboard context includes active session if running"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
        client.force_login(user)
        baker.make(Uczelnia, pbn_integracja=True)

        running_session = baker.make(
            ImportSession,
            user=user,
            status="running",
        )
        baker.make(
            ImportSession,
            user=user,
            status="completed",
        )

        response = client.get(reverse("pbn_import:dashboard"))

        assert response.context["active_session"] == running_session

    def test_dashboard_shows_only_user_sessions(self, django_user_model):
        """Test dashboard only shows sessions for logged-in user"""
        client = Client()
        user1 = baker.make(django_user_model, is_superuser=True)
        user2 = baker.make(django_user_model)
        client.force_login(user1)
        baker.make(Uczelnia, pbn_integracja=True)

        session1 = baker.make(ImportSession, user=user1)
        session2 = baker.make(ImportSession, user=user2)

        response = client.get(reverse("pbn_import:dashboard"))

        assert session1 in response.context["recent_sessions"]
        assert session2 not in response.context["recent_sessions"]


# ============================================================================
# START IMPORT VIEW TESTS
# ============================================================================


@pytest.mark.django_db
class TestStartImportView:
    """Test StartImportView"""

    def test_start_import_requires_permission(self, django_user_model):
        """Test start import requires permission"""
        client = Client()
        user = baker.make(django_user_model)
        client.force_login(user)

        response = client.post(reverse("pbn_import:start"))

        assert response.status_code == 403

    def test_start_import_creates_session(self, django_user_model):
        """Test start import creates ImportSession"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
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

    def test_start_import_stores_config(self, django_user_model):
        """Test start import stores configuration from POST data"""
        from bpp.models import Wydzial

        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
        uczelnia = baker.make(Uczelnia, pbn_integracja=True)
        wydzial = baker.make(Wydzial, nazwa="IT Department", uczelnia=uczelnia)
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
                    "wydzial_domyslny_id": wydzial.pk,
                },
            )

        session = ImportSession.objects.get(user=user)
        assert session.config["delete_existing"] is True
        assert session.config["wydzial_domyslny"] == "IT Department"
        assert session.config["wydzial_domyslny_id"] == wydzial.pk

    def test_start_import_redirects_to_dashboard(self, django_user_model):
        """Test start import redirects to dashboard after creation"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
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


# ============================================================================
# CANCEL IMPORT VIEW TESTS
# ============================================================================


@pytest.mark.django_db
class TestCancelImportView:
    """Test CancelImportView"""

    def test_cancel_import_requires_permission(self, django_user_model):
        """Test cancel import requires permission"""
        client = Client()
        user = baker.make(django_user_model)
        session = baker.make(ImportSession, user=user)
        client.force_login(user)

        response = client.post(reverse("pbn_import:cancel", args=[session.id]))

        assert response.status_code == 403

    def test_cancel_running_import(self, django_user_model):
        """Test cancelling a running import session"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
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

    def test_cancel_pending_import(self, django_user_model):
        """Test cancelling a pending import session"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
        session = baker.make(
            ImportSession,
            user=user,
            status="pending",
        )
        client.force_login(user)

        client.post(reverse("pbn_import:cancel", args=[session.id]))

        session.refresh_from_db()
        assert session.status == "cancelled"

    def test_cannot_cancel_completed_import(self, django_user_model):
        """Test cannot cancel already completed import"""
        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
        session = baker.make(
            ImportSession,
            user=user,
            status="completed",
        )
        client.force_login(user)

        client.post(reverse("pbn_import:cancel", args=[session.id]))

        session.refresh_from_db()
        assert session.status == "completed"  # Unchanged

    def test_cancel_creates_log_entry(self, django_user_model):
        """Test cancellation creates log entry"""
        from pbn_import.models import ImportLog

        client = Client()
        user = baker.make(django_user_model, is_superuser=True)
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

    def test_cancel_only_own_sessions(self, django_user_model):
        """Test user can only cancel their own sessions"""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        client = Client()
        user1 = baker.make(django_user_model, is_superuser=False)
        user2 = baker.make(django_user_model, is_superuser=False)
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
