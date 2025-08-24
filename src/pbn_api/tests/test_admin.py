from unittest.mock import patch

import pytest
from django.urls import reverse
from model_bakery import baker
from selenium.webdriver.support.wait import WebDriverWait

from pbn_api.admin import OswiadczeniaInstytucjiAdmin, PBN_Export_QueueAdmin
from pbn_api.client import PBN_DELETE_PUBLICATION_STATEMENT
from pbn_api.models import OswiadczenieInstytucji, PBN_Export_Queue, SentData
from pbn_api.tests.utils import middleware

from django.contrib.admin.sites import AdminSite
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages

from django_bpp.selenium_util import LONG_WAIT_TIME, wait_for, wait_for_page_load


def test_SentDataAdmin_list_filter_works(admin_client):
    url = reverse("admin:pbn_api_sentdata_changelist")
    res = admin_client.get(url + "?q=123")
    assert res.status_code == 200


def test_PublisherAdmin_search_works(admin_client):
    url = reverse("admin:pbn_api_publisher_changelist")
    res = admin_client.get(url + "?q=123")
    assert res.status_code == 200


@pytest.mark.django_db
def test_OswiadczenieInstytucji_delete_model(pbn_uczelnia, pbn_client, rf):
    oi = baker.make(OswiadczenieInstytucji)
    req = rf.get("/")

    pbn_client.transport.return_values[
        PBN_DELETE_PUBLICATION_STATEMENT.format(publicationId=oi.publicationId_id)
    ] = {"1": "2"}

    with middleware(req):
        OswiadczeniaInstytucjiAdmin(OswiadczenieInstytucji, None).delete_model(
            req, oi, pbn_client=pbn_client
        )

    try:
        OswiadczenieInstytucji.objects.get(pk=oi.pk)
        msg = list(get_messages(req))
        if msg:
            raise Exception(str(msg))
        raise Exception("Nie został skasowany")
    except OswiadczenieInstytucji.DoesNotExist:
        assert True  # good


@pytest.mark.django_db
def test_pbn_api_admin_SentDataAdmin_wyslij_ponownie(
    wydawnictwo_zwarte, admin_browser, channels_live_server
):
    s = SentData.objects.create(
        object_id=wydawnictwo_zwarte.pk,
        content_type=ContentType.objects.get_for_model(wydawnictwo_zwarte),
        data_sent={"foo": "bar"},
    )

    with wait_for_page_load(admin_browser):
        admin_browser.visit(
            channels_live_server.url + f"/admin/pbn_api/sentdata/{s.pk}/change"
        )

    wait_for(lambda: len(admin_browser.find_by_id("wyslij-ponownie")) > 0)

    elem = admin_browser.find_by_id("wyslij-ponownie")

    with wait_for_page_load(admin_browser):
        elem.click()

    WebDriverWait(admin_browser, LONG_WAIT_TIME).until(
        lambda *args, **kw: "nie będzie eksportowany" in admin_browser.html
    )
    assert True


# Tests for PBN_Export_QueueAdmin


@pytest.mark.django_db
def test_pbn_export_queue_admin_changelist_loads(admin_client):
    """Test that PBN_Export_Queue changelist loads without errors"""
    url = reverse("admin:pbn_api_pbn_export_queue_changelist")
    res = admin_client.get(url)
    assert res.status_code == 200


@pytest.mark.django_db
def test_pbn_export_queue_admin_search_works(admin_client):
    """Test that PBN_Export_Queue admin search works"""
    url = reverse("admin:pbn_api_pbn_export_queue_changelist")
    res = admin_client.get(url + "?q=testuser")
    assert res.status_code == 200


@pytest.mark.django_db
def test_pbn_export_queue_admin_resend_single_item(wydawnictwo_ciagle, admin_user):
    """Test the _resend_single_item method"""
    queue_item = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
        wysylke_zakonczono="2023-01-01 00:00:00",
        zakonczono_pomyslnie=True,
        retry_after_user_authorised=True,
    )

    admin_instance = PBN_Export_QueueAdmin(PBN_Export_Queue, AdminSite())

    with patch(
        "pbn_api.admin.pbn_export_queue.task_sprobuj_wyslac_do_pbn.delay"
    ) as mock_task:
        admin_instance._resend_single_item(queue_item, admin_user, " (test)")

        # Check that status fields were reset
        queue_item.refresh_from_db()
        assert queue_item.wysylke_zakonczono is None
        assert queue_item.zakonczono_pomyslnie is None
        assert queue_item.retry_after_user_authorised is None

        # Check that message was added to komunikat
        assert (
            f"Ponownie wysłano przez użytkownika: {admin_user} (test)"
            in queue_item.komunikat
        )

        # Check that task was called
        mock_task.assert_called_once_with(queue_item.pk)


@pytest.mark.django_db
def test_pbn_export_queue_admin_resend_action(wydawnictwo_ciagle, admin_user, rf):
    """Test the resend_to_pbn_action bulk action"""
    queue_item1 = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
        wysylke_zakonczono="2023-01-01 00:00:00",
        zakonczono_pomyslnie=True,
    )

    queue_item2 = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
        wysylke_zakonczono="2023-01-01 00:00:00",
        zakonczono_pomyslnie=False,
    )

    queryset = PBN_Export_Queue.objects.filter(pk__in=[queue_item1.pk, queue_item2.pk])

    request = rf.post("/")
    request.user = admin_user

    admin_instance = PBN_Export_QueueAdmin(PBN_Export_Queue, AdminSite())

    with middleware(request):
        with patch(
            "pbn_api.admin.pbn_export_queue.task_sprobuj_wyslac_do_pbn.delay"
        ) as mock_task:
            admin_instance.resend_to_pbn_action(request, queryset)

            # Check that both items were processed
            queue_item1.refresh_from_db()
            queue_item2.refresh_from_db()

            assert queue_item1.wysylke_zakonczono is None
            assert queue_item1.zakonczono_pomyslnie is None
            assert queue_item2.wysylke_zakonczono is None
            assert queue_item2.zakonczono_pomyslnie is None

            # Check that messages were added
            assert (
                f"Ponownie wysłano przez użytkownika: {admin_user} (akcja masowa)"
                in queue_item1.komunikat
            )
            assert (
                f"Ponownie wysłano przez użytkownika: {admin_user} (akcja masowa)"
                in queue_item2.komunikat
            )

            # Check that tasks were called for both items
            assert mock_task.call_count == 2


@pytest.mark.django_db
def test_pbn_export_queue_admin_response_change_resend(
    wydawnictwo_ciagle, admin_user, rf
):
    """Test the response_change method with _resend_to_pbn POST parameter"""
    queue_item = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
        wysylke_zakonczono="2023-01-01 00:00:00",
        zakonczono_pomyslnie=True,
    )

    request = rf.post("/", {"_resend_to_pbn": "true"})
    request.user = admin_user

    admin_instance = PBN_Export_QueueAdmin(PBN_Export_Queue, AdminSite())

    with middleware(request):
        with patch(
            "pbn_api.admin.pbn_export_queue.task_sprobuj_wyslac_do_pbn.delay"
        ) as mock_task:
            response = admin_instance.response_change(request, queue_item)

            # Check that we get a redirect response
            assert response.status_code == 302
            assert (
                f"/admin/pbn_api/pbn_export_queue/{queue_item.pk}/change/"
                in response.url
            )

            # Check that item was reset
            queue_item.refresh_from_db()
            assert queue_item.wysylke_zakonczono is None
            assert queue_item.zakonczono_pomyslnie is None

            # Check that task was called
            mock_task.assert_called_once_with(queue_item.pk)


@pytest.mark.django_db
def test_pbn_export_queue_admin_response_change_normal(
    wydawnictwo_ciagle, admin_user, rf
):
    """Test the response_change method with normal POST (no resend)"""
    queue_item = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
    )

    request = rf.post("/", {"_save": "true"})  # Normal save, not resend
    request.user = admin_user

    admin_instance = PBN_Export_QueueAdmin(PBN_Export_Queue, AdminSite())

    with middleware(request):
        with patch(
            "pbn_api.admin.pbn_export_queue.task_sprobuj_wyslac_do_pbn.delay"
        ) as mock_task:
            with patch.object(
                admin_instance.__class__.__bases__[0], "response_change"
            ) as mock_super:
                mock_super.return_value = "super_response"

                response = admin_instance.response_change(request, queue_item)

                # Check that super().response_change was called
                mock_super.assert_called_once_with(request, queue_item)
                assert response == "super_response"

                # Check that task was NOT called
                mock_task.assert_not_called()


@pytest.mark.django_db
def test_pbn_export_queue_admin_save_form(admin_user, rf):
    """Test save_form method returns form.save(commit=False)"""
    from django import forms

    class MockForm(forms.ModelForm):
        class Meta:
            model = PBN_Export_Queue
            fields = []

        def save(self, commit=True):
            return f"saved_with_commit_{commit}"

    request = rf.post("/")
    request.user = admin_user

    admin_instance = PBN_Export_QueueAdmin(PBN_Export_Queue, AdminSite())
    form = MockForm()

    result = admin_instance.save_form(request, form, change=True)
    assert result == "saved_with_commit_False"
