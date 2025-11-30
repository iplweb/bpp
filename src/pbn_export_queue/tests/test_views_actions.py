"""Tests for pbn_export_queue action views"""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from model_bakery import baker

from pbn_export_queue.models import PBN_Export_Queue

User = get_user_model()


# ============================================================================
# RESEND TO PBN VIEW TESTS
# ============================================================================


@pytest.mark.django_db
class TestResendToPbnView:
    """Tests for resend_to_pbn view function"""

    def test_resend_to_pbn_requires_login(self, client):
        """Test that unauthenticated users are redirected"""
        queue_item = baker.make(PBN_Export_Queue)
        url = reverse("pbn_export_queue:export-queue-resend", args=[queue_item.pk])
        response = client.post(url)

        assert response.status_code == 302

    def test_resend_to_pbn_requires_permission(self, client):
        """Test that users without permission get error"""
        user = baker.make(User)
        queue_item = baker.make(PBN_Export_Queue)

        client.force_login(user)
        url = reverse("pbn_export_queue:export-queue-resend", args=[queue_item.pk])
        response = client.post(url)

        assert response.status_code == 302

    def test_resend_to_pbn_success(self, client, admin_user):
        """Test successful resend"""
        queue_item = baker.make(
            PBN_Export_Queue,
            zamowil=admin_user,
            wysylke_zakonczono=None,
        )

        client.force_login(admin_user)
        url = reverse("pbn_export_queue:export-queue-resend", args=[queue_item.pk])

        with patch("pbn_export_queue.models.PBN_Export_Queue.sprobuj_wyslac_do_pbn"):
            response = client.post(url)

        assert response.status_code == 302
        queue_item.refresh_from_db()
        assert "przez" in queue_item.komunikat


# ============================================================================
# PREPARE FOR RESEND VIEW TESTS
# ============================================================================


@pytest.mark.django_db
class TestPrepareForResendView:
    """Tests for prepare_for_resend view function"""

    def test_prepare_for_resend_requires_permission(self, client):
        """Test that users without permission get error"""
        user = baker.make(User)
        queue_item = baker.make(PBN_Export_Queue)

        client.force_login(user)
        url = reverse(
            "pbn_export_queue:export-queue-prepare-resend", args=[queue_item.pk]
        )
        response = client.post(url)

        assert response.status_code == 302

    def test_prepare_for_resend_success(self, client, admin_user):
        """Test successful prepare for resend"""
        queue_item = baker.make(
            PBN_Export_Queue,
            zamowil=admin_user,
            wysylke_zakonczono=None,
        )

        client.force_login(admin_user)
        url = reverse(
            "pbn_export_queue:export-queue-prepare-resend", args=[queue_item.pk]
        )
        response = client.post(url)

        assert response.status_code == 302


# ============================================================================
# TRY SEND TO PBN VIEW TESTS
# ============================================================================


@pytest.mark.django_db
class TestTrySendToPbnView:
    """Tests for try_send_to_pbn view function"""

    def test_try_send_to_pbn_requires_permission(self, client):
        """Test that users without permission get error"""
        user = baker.make(User)
        queue_item = baker.make(PBN_Export_Queue)

        client.force_login(user)
        url = reverse("pbn_export_queue:export-queue-try-send", args=[queue_item.pk])
        response = client.post(url)

        assert response.status_code == 302

    def test_try_send_to_pbn_success(self, client, admin_user):
        """Test successful try send"""
        queue_item = baker.make(PBN_Export_Queue, zamowil=admin_user)

        client.force_login(admin_user)
        url = reverse("pbn_export_queue:export-queue-try-send", args=[queue_item.pk])

        with patch("pbn_export_queue.models.PBN_Export_Queue.sprobuj_wyslac_do_pbn"):
            response = client.post(url)

        assert response.status_code == 302


# ============================================================================
# RESEND ALL WAITING VIEW TESTS
# ============================================================================


@pytest.mark.django_db
class TestResendAllWaitingView:
    """Tests for resend_all_waiting view function"""

    def test_resend_all_waiting_requires_permission(self, client):
        """Test that users without permission get error"""
        user = baker.make(User)
        client.force_login(user)

        url = reverse("pbn_export_queue:export-queue-resend-all-waiting")
        response = client.post(url)

        assert response.status_code == 302

    def test_resend_all_waiting_no_items(self, client, admin_user):
        """Test message when no items to resend"""
        client.force_login(admin_user)
        url = reverse("pbn_export_queue:export-queue-resend-all-waiting")
        response = client.post(url)

        assert response.status_code == 302

    def test_resend_all_waiting_success(self, client, admin_user):
        """Test successful resend of all waiting items"""
        item1 = baker.make(
            PBN_Export_Queue,
            zamowil=admin_user,
            retry_after_user_authorised=True,
            wysylke_zakonczono=None,
        )
        item2 = baker.make(
            PBN_Export_Queue,
            zamowil=admin_user,
            retry_after_user_authorised=True,
            wysylke_zakonczono=None,
        )

        client.force_login(admin_user)
        url = reverse("pbn_export_queue:export-queue-resend-all-waiting")

        with patch("pbn_export_queue.models.PBN_Export_Queue.sprobuj_wyslac_do_pbn"):
            response = client.post(url)

        assert response.status_code == 302
        item1.refresh_from_db()
        item2.refresh_from_db()
        assert item1.wysylke_zakonczono is None
        assert item2.wysylke_zakonczono is None


# ============================================================================
# RESEND ALL ERRORS VIEW TESTS
# ============================================================================


@pytest.mark.django_db
class TestResendAllErrorsView:
    """Tests for resend_all_errors view function"""

    def test_resend_all_errors_requires_permission(self, client):
        """Test that users without permission get error"""
        user = baker.make(User)
        client.force_login(user)

        url = reverse("pbn_export_queue:export-queue-resend-all-errors")
        response = client.post(url)

        assert response.status_code == 302

    def test_resend_all_errors_no_items(self, client, admin_user):
        """Test message when no items to resend"""
        client.force_login(admin_user)
        url = reverse("pbn_export_queue:export-queue-resend-all-errors")
        response = client.post(url)

        assert response.status_code == 302

    def test_resend_all_errors_success(self, client, admin_user):
        """Test successful resend of all error items"""
        item1 = baker.make(
            PBN_Export_Queue,
            zamowil=admin_user,
            zakonczono_pomyslnie=False,
        )
        item2 = baker.make(
            PBN_Export_Queue,
            zamowil=admin_user,
            zakonczono_pomyslnie=False,
        )

        client.force_login(admin_user)
        url = reverse("pbn_export_queue:export-queue-resend-all-errors")

        with patch("pbn_export_queue.models.PBN_Export_Queue.sprobuj_wyslac_do_pbn"):
            response = client.post(url)

        assert response.status_code == 302
        item1.refresh_from_db()
        item2.refresh_from_db()


# ============================================================================
# COUNTS VIEW TESTS
# ============================================================================


@pytest.mark.django_db
class TestPBNExportQueueCountsView:
    """Tests for PBNExportQueueCountsView"""

    def test_counts_view_requires_login(self, client):
        """Test that unauthenticated users are redirected"""
        url = reverse("pbn_export_queue:export-queue-counts")
        response = client.get(url)

        assert response.status_code == 302

    def test_counts_view_requires_permission(self, client):
        """Test that users without permission get 403"""
        user = baker.make(User)
        client.force_login(user)

        url = reverse("pbn_export_queue:export-queue-counts")
        response = client.get(url)

        assert response.status_code == 403

    def test_counts_view_returns_counts(self, client, admin_user):
        """Test that counts view returns correct counts"""
        baker.make(
            PBN_Export_Queue,
            zamowil=admin_user,
            zakonczono_pomyslnie=True,
        )
        baker.make(
            PBN_Export_Queue,
            zamowil=admin_user,
            zakonczono_pomyslnie=False,
        )
        baker.make(
            PBN_Export_Queue,
            zamowil=admin_user,
            zakonczono_pomyslnie=None,
        )

        client.force_login(admin_user)
        url = reverse("pbn_export_queue:export-queue-counts")
        response = client.get(url)

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 3
        assert data["success_count"] == 1
        assert data["error_count"] == 1
        assert data["pending_count"] == 1
        assert data["waiting_count"] == 0
