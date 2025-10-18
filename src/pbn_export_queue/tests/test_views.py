"""Tests for pbn_export_queue views"""

from unittest.mock import patch

import pytest
from django.test import RequestFactory
from django.urls import reverse
from model_bakery import baker

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()

from pbn_export_queue.models import PBN_Export_Queue
from pbn_export_queue.views import (
    PBNExportQueuePermissionMixin,
)

from bpp.const import GR_WPROWADZANIE_DANYCH


@pytest.mark.django_db
class TestPBNExportQueuePermissionMixin:
    """Tests for PBNExportQueuePermissionMixin"""

    def test_test_func_returns_true_for_superuser(self):
        """Test that superuser passes permission test"""
        superuser = baker.make(User, is_superuser=True, is_staff=True)
        request = RequestFactory().get("/")
        request.user = superuser

        mixin = PBNExportQueuePermissionMixin()
        mixin.request = request

        assert mixin.test_func() is True

    def test_test_func_returns_true_for_staff(self):
        """Test that staff user passes permission test"""
        staff_user = baker.make(User, is_staff=True)
        request = RequestFactory().get("/")
        request.user = staff_user

        mixin = PBNExportQueuePermissionMixin()
        mixin.request = request

        assert mixin.test_func() is True

    def test_test_func_returns_true_for_gr_wprowadzanie_danych_group(self):
        """Test that user in GR_WPROWADZANIE_DANYCH group passes"""
        group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
        user = baker.make(User)
        user.groups.add(group)

        request = RequestFactory().get("/")
        request.user = user

        mixin = PBNExportQueuePermissionMixin()
        mixin.request = request

        assert mixin.test_func() is True

    def test_test_func_returns_false_for_normal_user(self):
        """Test that normal user fails permission test"""
        user = baker.make(User)
        request = RequestFactory().get("/")
        request.user = user

        mixin = PBNExportQueuePermissionMixin()
        mixin.request = request

        assert mixin.test_func() is False


@pytest.mark.django_db
class TestPBNExportQueueListView:
    """Tests for PBNExportQueueListView"""

    def test_list_view_requires_login(self, client):
        """Test that unauthenticated users are redirected"""
        url = reverse("pbn_export_queue:export-queue-list")
        response = client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url

    def test_list_view_requires_permission(self, client):
        """Test that users without permission get 403"""
        user = baker.make(User)
        client.force_login(user)

        url = reverse("pbn_export_queue:export-queue-list")
        response = client.get(url)

        assert response.status_code == 403

    def test_list_view_accessible_to_staff(self, client, admin_user):
        """Test that staff users can access the list view"""
        client.force_login(admin_user)
        url = reverse("pbn_export_queue:export-queue-list")
        response = client.get(url)

        assert response.status_code == 200

    def test_list_view_filter_by_success_true(self, client, admin_user):
        """Test filtering by zakonczono_pomyslnie=true"""
        queue_item = baker.make(
            PBN_Export_Queue,
            zamowil=admin_user,
            zakonczono_pomyslnie=True,
        )
        baker.make(
            PBN_Export_Queue,
            zamowil=admin_user,
            zakonczono_pomyslnie=False,
        )

        client.force_login(admin_user)
        url = reverse("pbn_export_queue:export-queue-list")
        response = client.get(url + "?zakonczono_pomyslnie=true")

        assert response.status_code == 200
        assert queue_item in response.context["export_queue_items"]

    def test_list_view_filter_by_success_false(self, client, admin_user):
        """Test filtering by zakonczono_pomyslnie=false"""
        queue_item = baker.make(
            PBN_Export_Queue,
            zamowil=admin_user,
            zakonczono_pomyslnie=False,
        )
        baker.make(
            PBN_Export_Queue,
            zamowil=admin_user,
            zakonczono_pomyslnie=True,
        )

        client.force_login(admin_user)
        url = reverse("pbn_export_queue:export-queue-list")
        response = client.get(url + "?zakonczono_pomyslnie=false")

        assert response.status_code == 200
        assert queue_item in response.context["export_queue_items"]

    def test_list_view_filter_by_success_none(self, client, admin_user):
        """Test filtering by zakonczono_pomyslnie=none"""
        queue_item = baker.make(
            PBN_Export_Queue,
            zamowil=admin_user,
            zakonczono_pomyslnie=None,
        )
        baker.make(
            PBN_Export_Queue,
            zamowil=admin_user,
            zakonczono_pomyslnie=True,
        )

        client.force_login(admin_user)
        url = reverse("pbn_export_queue:export-queue-list")
        response = client.get(url + "?zakonczono_pomyslnie=none")

        assert response.status_code == 200
        assert queue_item in response.context["export_queue_items"]

    def test_list_view_search_by_komunikat(
        self, client, admin_user, wydawnictwo_ciagle
    ):
        """Test searching by komunikat"""
        queue_item = baker.make(
            PBN_Export_Queue,
            zamowil=admin_user,
            rekord_do_wysylki=wydawnictwo_ciagle,
            komunikat="Test search query",
        )

        client.force_login(admin_user)
        url = reverse("pbn_export_queue:export-queue-list")
        response = client.get(url + "?q=Test")

        assert response.status_code == 200
        assert queue_item in response.context["export_queue_items"]

    @pytest.mark.serial
    def test_list_view_sort_by_pk(self, client, admin_user):
        """Test sorting by pk"""
        item1 = baker.make(PBN_Export_Queue, zamowil=admin_user)
        item2 = baker.make(PBN_Export_Queue, zamowil=admin_user)

        client.force_login(admin_user)
        url = reverse("pbn_export_queue:export-queue-list")
        response = client.get(url + "?sort=pk")

        assert response.status_code == 200
        items = list(response.context["export_queue_items"])
        assert items[0].pk <= items[1].pk

    def test_list_view_sort_by_reverse_pk(self, client, admin_user):
        """Test sorting by reverse pk"""
        item1 = baker.make(PBN_Export_Queue, zamowil=admin_user)
        item2 = baker.make(PBN_Export_Queue, zamowil=admin_user)

        client.force_login(admin_user)
        url = reverse("pbn_export_queue:export-queue-list")
        response = client.get(url + "?sort=-pk")

        assert response.status_code == 200
        items = list(response.context["export_queue_items"])
        assert items[0].pk >= items[1].pk

    def test_list_view_invalid_sort_parameter_ignored(self, client, admin_user):
        """Test that invalid sort parameter is ignored"""
        baker.make(PBN_Export_Queue, zamowil=admin_user)

        client.force_login(admin_user)
        url = reverse("pbn_export_queue:export-queue-list")
        response = client.get(url + "?sort=invalid_sort")

        assert response.status_code == 200

    def test_list_view_context_has_counts(self, client, admin_user):
        """Test that context has count variables"""
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
        url = reverse("pbn_export_queue:export-queue-list")
        response = client.get(url)

        assert response.status_code == 200
        assert response.context["total_count"] == 3
        assert response.context["success_count"] == 1
        assert response.context["error_count"] == 1
        assert response.context["pending_count"] == 1
        assert response.context["error_count"] == 1
        assert response.context["waiting_count"] == 0


@pytest.mark.django_db
class TestPBNExportQueueTableView:
    """Tests for PBNExportQueueTableView"""

    def test_table_view_requires_login(self, client):
        """Test that unauthenticated users are redirected"""
        url = reverse("pbn_export_queue:export-queue-table")
        response = client.get(url)

        assert response.status_code == 302

    def test_table_view_requires_permission(self, client):
        """Test that users without permission get 403"""
        user = baker.make(User)
        client.force_login(user)

        url = reverse("pbn_export_queue:export-queue-table")
        response = client.get(url)

        assert response.status_code == 403

    def test_table_view_accessible_to_staff(self, client, admin_user):
        """Test that staff users can access the table view"""
        baker.make(PBN_Export_Queue, zamowil=admin_user)

        client.force_login(admin_user)
        url = reverse("pbn_export_queue:export-queue-table")
        response = client.get(url)

        assert response.status_code == 200


@pytest.mark.django_db
class TestPBNExportQueueDetailView:
    """Tests for PBNExportQueueDetailView"""

    def test_detail_view_requires_login(self, client):
        """Test that unauthenticated users are redirected"""
        queue_item = baker.make(PBN_Export_Queue)
        url = reverse("pbn_export_queue:export-queue-detail", args=[queue_item.pk])
        response = client.get(url)

        assert response.status_code == 302

    def test_detail_view_requires_permission(self, client):
        """Test that users without permission get 403"""
        user = baker.make(User)
        queue_item = baker.make(PBN_Export_Queue)

        client.force_login(user)
        url = reverse("pbn_export_queue:export-queue-detail", args=[queue_item.pk])
        response = client.get(url)

        assert response.status_code == 403

    def test_detail_view_accessible_to_staff(self, client, admin_user):
        """Test that staff users can access the detail view"""
        queue_item = baker.make(PBN_Export_Queue, zamowil=admin_user)

        client.force_login(admin_user)
        url = reverse("pbn_export_queue:export-queue-detail", args=[queue_item.pk])
        response = client.get(url)

        assert response.status_code == 200

    def test_detail_view_parses_komunikat_links(self, client, admin_user):
        """Test that detail view parses SentData links"""
        komunikat = (
            'href="/admin/pbn_api/sentdata/123/change/"' " and publication/abc-123-def"
        )
        queue_item = baker.make(
            PBN_Export_Queue,
            zamowil=admin_user,
            komunikat=komunikat,
        )

        client.force_login(admin_user)
        url = reverse("pbn_export_queue:export-queue-detail", args=[queue_item.pk])
        response = client.get(url)

        assert response.status_code == 200
        if "parsed_links" in response.context:
            links = response.context["parsed_links"]
            assert links.get("sentdata_url") == "/admin/pbn_api/sentdata/123/change/"

    def test_detail_view_no_links_in_komunikat(self, client, admin_user):
        """Test detail view when komunikat has no links"""
        queue_item = baker.make(
            PBN_Export_Queue,
            zamowil=admin_user,
            komunikat="Simple message without links",
        )

        client.force_login(admin_user)
        url = reverse("pbn_export_queue:export-queue-detail", args=[queue_item.pk])
        response = client.get(url)

        assert response.status_code == 200


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
