"""Unit tests for PBN import traceback visibility and permissions"""

import pytest
from django.test import Client
from django.urls import reverse
from model_bakery import baker

from pbn_import.models import ImportLog, ImportSession

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

        assert "Traceback" in content
        assert "ValueError: Test error" in content
        assert "tylko dla superużytkowników" in content or "superuser" in content

    def test_regular_user_cannot_see_traceback_in_session_detail(
        self, django_user_model
    ):
        """Test that regular users cannot see tracebacks in session detail"""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        client = Client()
        regular_user = baker.make(django_user_model, is_superuser=False)

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

        assert "Test error message" in content
        assert "Traceback (most recent call last)" not in content
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

        assert "Error occurred" in content

    def test_regular_user_cannot_see_traceback_in_log_details(self, django_user_model):
        """Test that regular users cannot see tracebacks in ImportLog details"""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        client = Client()
        regular_user = baker.make(django_user_model, is_superuser=False)

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

        assert "Error occurred" in content
        assert "tylko dla superużytkowników" in content
