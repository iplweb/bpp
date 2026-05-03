"""Integration tests for pbn_wysylka_oswiadczen app."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import RequestFactory
from django.urls import reverse

from bpp.const import GR_WPROWADZANIE_DANYCH
from pbn_wysylka_oswiadczen.queries import get_publications_queryset
from pbn_wysylka_oswiadczen.views import PbnWysylkaOswiadczenMainView

from ._helpers import create_user_with_group

User = get_user_model()


@pytest.mark.django_db
def test_full_workflow_no_publications(client, uczelnia):
    """Test full workflow when no publications match criteria."""
    user = User.objects.create_user("testuser", password="testpass")
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(group)

    client.force_login(user)

    response = client.get(reverse("pbn_wysylka_oswiadczen:main"))
    assert response.status_code == 200
    assert b"0" in response.content  # Total count should be 0


@pytest.mark.django_db
def test_main_view_authenticated(client, uczelnia):
    """Test main view for authenticated user with proper group."""
    user = User.objects.create_user("testuser", password="testpass")
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(group)

    client.force_login(user)

    response = client.get(reverse("pbn_wysylka_oswiadczen:main"))
    assert response.status_code == 200
    assert "Wysyłka oświadczeń" in response.content.decode("utf-8")


@pytest.mark.django_db
def test_main_view_unauthenticated(client):
    """Test main view redirects unauthenticated users."""
    response = client.get(reverse("pbn_wysylka_oswiadczen:main"))
    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_status_api_returns_json(client, uczelnia):
    """Test status API returns valid JSON."""
    user = User.objects.create_user("testuser", password="testpass")
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(group)

    client.force_login(user)

    response = client.get(reverse("pbn_wysylka_oswiadczen:status"))
    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"

    data = response.json()
    assert "is_running" in data
    assert "latest_task" in data


@pytest.mark.django_db
def test_get_publications_queryset_tylko_odpiete_parameter(uczelnia):
    """Test get_publications_queryset accepts tylko_odpiete parameter."""
    # Test with tylko_odpiete=False (default)
    ciagle_qs, zwarte_qs = get_publications_queryset(
        rok_od=2022, rok_do=2025, tylko_odpiete=False, with_annotations=True
    )
    assert ciagle_qs.count() == 0
    assert zwarte_qs.count() == 0

    # Test with tylko_odpiete=True
    ciagle_qs, zwarte_qs = get_publications_queryset(
        rok_od=2022, rok_do=2025, tylko_odpiete=True, with_annotations=True
    )
    assert ciagle_qs.count() == 0
    assert zwarte_qs.count() == 0


@pytest.mark.django_db
def test_main_view_context_tylko_odpiete(uczelnia):
    """Test main view returns tylko_odpiete in context."""
    factory = RequestFactory()
    request = factory.get("/?rok_od=2022&rok_do=2024&tylko_odpiete=true")

    user = create_user_with_group()
    request.user = user
    request.session = {}

    view = PbnWysylkaOswiadczenMainView()
    view.setup(request)

    context = view.get_context_data()
    assert "tylko_odpiete" in context
    assert context["tylko_odpiete"] is True


@pytest.mark.django_db
def test_main_view_context_tylko_odpiete_false(uczelnia):
    """Test main view returns tylko_odpiete=False when not set."""
    factory = RequestFactory()
    request = factory.get("/?rok_od=2022&rok_do=2024")

    user = create_user_with_group()
    request.user = user
    request.session = {}

    view = PbnWysylkaOswiadczenMainView()
    view.setup(request)

    context = view.get_context_data()
    assert "tylko_odpiete" in context
    assert context["tylko_odpiete"] is False
