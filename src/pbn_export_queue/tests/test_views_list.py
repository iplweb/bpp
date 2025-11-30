"""Tests for pbn_export_queue list and table views"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import RequestFactory
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from pbn_export_queue.models import PBN_Export_Queue
from pbn_export_queue.views import PBNExportQueuePermissionMixin

User = get_user_model()


# ============================================================================
# PERMISSION MIXIN TESTS
# ============================================================================


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


# ============================================================================
# LIST VIEW TESTS
# ============================================================================


@pytest.mark.django_db
def test_pbnexportqueuelistview_requires_login(client):
    """Test that unauthenticated users are redirected"""
    url = reverse("pbn_export_queue:export-queue-list")
    response = client.get(url)

    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_pbnexportqueuelistview_requires_permission(client):
    """Test that users without permission get 403"""
    user = baker.make(User)
    client.force_login(user)

    url = reverse("pbn_export_queue:export-queue-list")
    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_pbnexportqueuelistview_accessible_to_staff(client, admin_user):
    """Test that staff users can access the list view"""
    client.force_login(admin_user)
    url = reverse("pbn_export_queue:export-queue-list")
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_pbnexportqueuelistview_filter_by_success_true(
    client, admin_user, wydawnictwo_ciagle
):
    """Test filtering by zakonczono_pomyslnie=true"""
    queue_item = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
        zakonczono_pomyslnie=True,
    )
    baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
        zakonczono_pomyslnie=False,
    )

    client.force_login(admin_user)
    url = reverse("pbn_export_queue:export-queue-list")
    response = client.get(url + "?zakonczono_pomyslnie=true")

    assert response.status_code == 200
    assert queue_item in response.context["export_queue_items"]


@pytest.mark.django_db
def test_pbnexportqueuelistview_filter_by_success_false(
    client, admin_user, wydawnictwo_ciagle
):
    """Test filtering by zakonczono_pomyslnie=false"""
    queue_item = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
        zakonczono_pomyslnie=False,
    )
    baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
        zakonczono_pomyslnie=True,
    )

    client.force_login(admin_user)
    url = reverse("pbn_export_queue:export-queue-list")
    response = client.get(url + "?zakonczono_pomyslnie=false")

    assert response.status_code == 200
    assert queue_item in response.context["export_queue_items"]


@pytest.mark.django_db
def test_pbnexportqueuelistview_filter_by_success_none(
    client, admin_user, wydawnictwo_ciagle
):
    """Test filtering by zakonczono_pomyslnie=none"""
    queue_item = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
        zakonczono_pomyslnie=None,
    )
    baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
        zakonczono_pomyslnie=True,
    )

    client.force_login(admin_user)
    url = reverse("pbn_export_queue:export-queue-list")
    response = client.get(url + "?zakonczono_pomyslnie=none")

    assert response.status_code == 200
    assert queue_item in response.context["export_queue_items"]


@pytest.mark.django_db
def test_pbnexportqueuelistview_search_by_komunikat(
    client, admin_user, wydawnictwo_ciagle
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


@pytest.mark.django_db
@pytest.mark.serial
def test_pbnexportqueuelistview_sort_by_pk(client, admin_user, wydawnictwo_ciagle):
    """Test sorting by pk"""
    baker.make(
        PBN_Export_Queue, rekord_do_wysylki=wydawnictwo_ciagle, zamowil=admin_user
    )
    baker.make(
        PBN_Export_Queue, rekord_do_wysylki=wydawnictwo_ciagle, zamowil=admin_user
    )

    client.force_login(admin_user)
    url = reverse("pbn_export_queue:export-queue-list")
    response = client.get(url + "?sort=pk")

    assert response.status_code == 200
    items = list(response.context["export_queue_items"])
    assert items[0].pk <= items[1].pk


@pytest.mark.django_db
def test_pbnexportqueuelistview_sort_by_reverse_pk(
    client, admin_user, wydawnictwo_ciagle
):
    """Test sorting by reverse pk"""
    baker.make(
        PBN_Export_Queue, rekord_do_wysylki=wydawnictwo_ciagle, zamowil=admin_user
    )
    baker.make(
        PBN_Export_Queue, rekord_do_wysylki=wydawnictwo_ciagle, zamowil=admin_user
    )

    client.force_login(admin_user)
    url = reverse("pbn_export_queue:export-queue-list")
    response = client.get(url + "?sort=-pk")

    assert response.status_code == 200
    items = list(response.context["export_queue_items"])
    assert items[0].pk >= items[1].pk


@pytest.mark.django_db
def test_pbnexportqueuelistview_invalid_sort_parameter_ignored(
    client, admin_user, wydawnictwo_ciagle
):
    """Test that invalid sort parameter is ignored"""
    baker.make(
        PBN_Export_Queue, rekord_do_wysylki=wydawnictwo_ciagle, zamowil=admin_user
    )

    client.force_login(admin_user)
    url = reverse("pbn_export_queue:export-queue-list")
    response = client.get(url + "?sort=invalid_sort")

    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.serial
def test_pbnexportqueuelistview_context_has_counts(
    client, admin_user, wydawnictwo_ciagle
):
    """Test that context has count variables"""
    baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
        zakonczono_pomyslnie=True,
    )
    baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
        zakonczono_pomyslnie=False,
    )
    baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
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


# ============================================================================
# TABLE VIEW TESTS
# ============================================================================


@pytest.mark.django_db
def test_pbnexportqueuetableview_requires_login(client):
    """Test that unauthenticated users are redirected"""
    url = reverse("pbn_export_queue:export-queue-table")
    response = client.get(url)

    assert response.status_code == 302


@pytest.mark.django_db
def test_pbnexportqueuetableview_requires_permission(client):
    """Test that users without permission get 403"""
    user = baker.make(User)
    client.force_login(user)

    url = reverse("pbn_export_queue:export-queue-table")
    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_pbnexportqueuetableview_accessible_to_staff(
    client, admin_user, wydawnictwo_ciagle
):
    """Test that staff users can access the table view"""
    baker.make(
        PBN_Export_Queue, rekord_do_wysylki=wydawnictwo_ciagle, zamowil=admin_user
    )

    client.force_login(admin_user)
    url = reverse("pbn_export_queue:export-queue-table")
    response = client.get(url)

    assert response.status_code == 200
