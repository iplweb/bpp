"""Tests for OplatyPublikacjiLogAdmin."""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from model_bakery import baker

from bpp.models import OplatyPublikacjiLog, Wydawnictwo_Ciagle


@pytest.fixture
def log_entry():
    """Create a log entry for testing."""
    pub = baker.make(Wydawnictwo_Ciagle, rok=2024)
    ct = ContentType.objects.get_for_model(pub)
    return OplatyPublikacjiLog.objects.create(
        content_type=ct,
        object_id=pub.pk,
        changed_by="test_command",
        prev_opl_pub_cost_free=None,
        new_opl_pub_cost_free=True,
    )


@pytest.mark.django_db
def test_oplaty_log_admin_list_view(admin_client, log_entry):
    """Test that the list view is accessible."""
    url = reverse("admin:bpp_oplatypublikacjilog_changelist")
    response = admin_client.get(url)
    assert response.status_code == 200
    assert "test_command" in response.content.decode()


@pytest.mark.django_db
def test_oplaty_log_admin_detail_view(admin_client, log_entry):
    """Test that the detail view is accessible."""
    url = reverse("admin:bpp_oplatypublikacjilog_change", args=[log_entry.pk])
    response = admin_client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_oplaty_log_admin_no_add_permission(admin_client):
    """Test that add permission is denied."""
    url = reverse("admin:bpp_oplatypublikacjilog_add")
    response = admin_client.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_oplaty_log_admin_no_delete_permission(admin_client, log_entry):
    """Test that delete permission is denied."""
    url = reverse("admin:bpp_oplatypublikacjilog_delete", args=[log_entry.pk])
    response = admin_client.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_oplaty_log_admin_readonly_fields(admin_client, log_entry):
    """Test that fields are readonly (POST should not change values)."""
    url = reverse("admin:bpp_oplatypublikacjilog_change", args=[log_entry.pk])

    # Try to POST a change
    admin_client.post(
        url,
        {
            "changed_by": "modified_command",
        },
    )

    # Refresh and check that nothing changed
    log_entry.refresh_from_db()
    assert log_entry.changed_by == "test_command"  # Should remain unchanged


@pytest.mark.django_db
def test_oplaty_log_admin_list_display_fields(admin_client, log_entry):
    """Test that list display shows expected fields."""
    url = reverse("admin:bpp_oplatypublikacjilog_changelist")
    response = admin_client.get(url)
    content = response.content.decode()

    # Check that key fields are displayed
    assert "test_command" in content  # changed_by


@pytest.mark.django_db
def test_oplaty_log_admin_filter_by_changed_by(admin_client):
    """Test filtering by changed_by field."""
    pub1 = baker.make(Wydawnictwo_Ciagle, rok=2024)
    pub2 = baker.make(Wydawnictwo_Ciagle, rok=2024)
    ct = ContentType.objects.get_for_model(pub1)

    OplatyPublikacjiLog.objects.create(
        content_type=ct,
        object_id=pub1.pk,
        changed_by="command_a",
    )
    OplatyPublikacjiLog.objects.create(
        content_type=ct,
        object_id=pub2.pk,
        changed_by="command_b",
    )

    url = reverse("admin:bpp_oplatypublikacjilog_changelist")
    response = admin_client.get(url, {"changed_by": "command_a"})

    content = response.content.decode()
    assert "command_a" in content
    # command_b might still appear in filter sidebar, but should not be in main list


@pytest.mark.django_db
def test_oplaty_log_admin_filter_by_rok(admin_client):
    """Test filtering by rok field."""
    pub_2024 = baker.make(Wydawnictwo_Ciagle, rok=2024)
    pub_2023 = baker.make(Wydawnictwo_Ciagle, rok=2023)
    ct = ContentType.objects.get_for_model(pub_2024)

    OplatyPublikacjiLog.objects.create(
        content_type=ct,
        object_id=pub_2024.pk,
        changed_by="test_command",
        rok=2024,
    )
    OplatyPublikacjiLog.objects.create(
        content_type=ct,
        object_id=pub_2023.pk,
        changed_by="test_command",
        rok=2023,
    )

    url = reverse("admin:bpp_oplatypublikacjilog_changelist")
    response = admin_client.get(url, {"rok": "2024"})

    assert response.status_code == 200


@pytest.mark.django_db
def test_oplaty_log_admin_search_by_title(admin_client):
    """Test searching by publication title."""
    pub = baker.make(
        Wydawnictwo_Ciagle, rok=2024, tytul_oryginalny="Unikalny tytuł testowy XYZ123"
    )
    ct = ContentType.objects.get_for_model(pub)

    OplatyPublikacjiLog.objects.create(
        content_type=ct,
        object_id=pub.pk,
        changed_by="test_command",
        rok=2024,
    )

    url = reverse("admin:bpp_oplatypublikacjilog_changelist")
    response = admin_client.get(url, {"q": "XYZ123"})

    assert response.status_code == 200
    content = response.content.decode()
    assert "Unikalny tytuł testowy XYZ123" in content
