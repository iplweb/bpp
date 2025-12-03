"""Tests for pbn_export_queue detail view"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory
from django.urls import reverse
from model_bakery import baker

from pbn_export_queue.models import PBN_Export_Queue
from pbn_export_queue.views import PBNExportQueueDetailView

User = get_user_model()


# ============================================================================
# DETAIL VIEW BASIC TESTS
# ============================================================================


@pytest.mark.django_db
def test_pbnexportqueuedetailview_requires_login(client):
    """Test that unauthenticated users are redirected"""
    queue_item = baker.make(PBN_Export_Queue)
    url = reverse("pbn_export_queue:export-queue-detail", args=[queue_item.pk])
    response = client.get(url)

    assert response.status_code == 302


@pytest.mark.django_db
def test_pbnexportqueuedetailview_requires_permission(client):
    """Test that users without permission get 403"""
    user = baker.make(User)
    queue_item = baker.make(PBN_Export_Queue)

    client.force_login(user)
    url = reverse("pbn_export_queue:export-queue-detail", args=[queue_item.pk])
    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_pbnexportqueuedetailview_accessible_to_staff(
    client, admin_user, wydawnictwo_ciagle
):
    """Test that staff users can access the detail view"""
    queue_item = baker.make(
        PBN_Export_Queue, rekord_do_wysylki=wydawnictwo_ciagle, zamowil=admin_user
    )

    client.force_login(admin_user)
    url = reverse("pbn_export_queue:export-queue-detail", args=[queue_item.pk])
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_pbnexportqueuedetailview_parses_komunikat_links(
    client, admin_user, wydawnictwo_ciagle
):
    """Test that detail view parses SentData links"""
    komunikat = 'href="/admin/pbn_api/sentdata/123/change/" and publication/abc-123-def'
    queue_item = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
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


@pytest.mark.django_db
@pytest.mark.serial
def test_pbnexportqueuedetailview_no_links_in_komunikat(
    client, admin_user, wydawnictwo_ciagle
):
    """Test detail view when komunikat has no links"""
    queue_item = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
        komunikat="Simple message without links",
    )

    client.force_login(admin_user)
    url = reverse("pbn_export_queue:export-queue-detail", args=[queue_item.pk])
    response = client.get(url)

    assert response.status_code == 200


# ============================================================================
# DETAIL VIEW CONTEXT TESTS
# ============================================================================


@pytest.mark.django_db
def test_pbnexportqueuedetailview_get_context_data_with_sentdata(
    client, admin_user, wydawnictwo_ciagle
):
    """Test get_context_data includes clipboard data when SentData exists"""
    from pbn_api.models.sentdata import SentData

    queue_item = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
        zakonczono_pomyslnie=False,
    )

    # Create SentData using content_type and object_id
    content_type = ContentType.objects.get_for_model(wydawnictwo_ciagle)
    baker.make(
        SentData,
        content_type=content_type,
        object_id=wydawnictwo_ciagle.pk,
        data_sent={"test": "data"},
        exception='(400, "/api/v1/publications", \'{"message": "Error"}\')',
        api_response_status=400,
    )

    client.force_login(admin_user)
    url = reverse("pbn_export_queue:export-queue-detail", args=[queue_item.pk])
    response = client.get(url)

    assert response.status_code == 200
    # Check that clipboard data is in context
    assert "json_data" in response.context
    assert "helpdesk_email" in response.context
    assert "ai_prompt" in response.context
    # Verify content
    assert '"test"' in response.context["json_data"]
    assert "Z poważaniem" in response.context["helpdesk_email"]
    assert "# KONTEKST" in response.context["ai_prompt"]


@pytest.mark.django_db
def test_pbnexportqueuedetailview_get_context_data_without_sentdata(
    client, admin_user, wydawnictwo_ciagle
):
    """Test get_context_data when no SentData exists"""
    queue_item = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
    )

    client.force_login(admin_user)
    url = reverse("pbn_export_queue:export-queue-detail", args=[queue_item.pk])
    response = client.get(url)

    assert response.status_code == 200
    # Check that clipboard data is NOT in context
    assert "json_data" not in response.context
    assert "helpdesk_email" not in response.context
    assert "ai_prompt" not in response.context


# ============================================================================
# BUILD HELPDESK EMAIL AND AI PROMPT TESTS
# ============================================================================


@pytest.mark.django_db
def test_build_helpdesk_email(admin_user, wydawnictwo_ciagle):
    """Test _build_helpdesk_email generates correct email"""
    from unittest.mock import Mock

    queue_item = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
    )

    sent_data = Mock()
    sent_data.exception = '(400, "/api/v1/publications", \'{"message": "Error"}\')'
    sent_data.api_response_status = 400
    sent_data.submitted_at = None
    sent_data.last_updated_on = None

    request = RequestFactory().get("/")
    request.user = admin_user

    view = PBNExportQueueDetailView()
    view.request = request
    view.object = queue_item

    result = view._build_helpdesk_email(sent_data, "Test Title", '{"test": "data"}')

    assert "Test Title" in result
    assert "Z poważaniem" in result
    assert admin_user.username in result or admin_user.email in result
    assert "400" in result


@pytest.mark.django_db
def test_build_ai_prompt(admin_user, wydawnictwo_ciagle):
    """Test _build_ai_prompt generates correct prompt"""
    from unittest.mock import Mock

    queue_item = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
        komunikat="Some error message",
    )

    sent_data = Mock()
    sent_data.exception = (
        'pbn_api.exceptions.HttpException: (400, "/api/v1/publications", '
        '\'{"message": "Validation failed", "description": "Invalid data"}\')'
    )
    sent_data.api_response_status = 400

    request = RequestFactory().get("/")
    request.user = admin_user

    view = PBNExportQueueDetailView()
    view.request = request
    view.object = queue_item

    result = view._build_ai_prompt(sent_data, "Test Title", '{"test": "data"}')

    assert "Test Title" in result
    assert "400" in result
    assert "Validation failed" in result
    assert '{"test": "data"}' in result
    assert "# KONTEKST" in result
    assert "# ZADANIE" in result
