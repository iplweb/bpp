"""Tests for RaportSlotowUczelnia API viewset.

Scoping analysis (Task 9, Part A):
  Both `RaportSlotowUczelniaViewSet.get_queryset` and
  `RaportSlotowUczelniaWierszViewSet.get_queryset` are scoped by
  `owner=request.user` / `parent__owner=request.user`.  Per-user ownership
  already prevents cross-university leakage — a user can only see their own
  reports regardless of which uczelnia the report was created for.
  No redundant uczelnia filter was added.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker
from rest_framework.test import APIClient

from bpp import const
from raport_slotow.models.uczelnia import RaportSlotowUczelnia

User = get_user_model()


def _make_api_user(username, password="testpass123"):
    """Create a user in the 'generowanie raportów' group."""
    user = User.objects.create_user(username=username, password=password)
    group, _ = Group.objects.get_or_create(name=const.GR_RAPORTY_WYSWIETLANIE)
    user.groups.add(group)
    return user, password


@pytest.mark.django_db
def test_raport_slotow_uczelnia_user_sees_only_own_report():
    """A user can only see reports owned by themselves.

    owner-scoped queryset: filter(owner=request.user) prevents user_b from
    seeing user_a's report, which transitively covers multi-uczelnia isolation
    (no user will see another university's reports via someone else's account).
    """
    user_a, pw_a = _make_api_user("user_raport_a")
    user_b, pw_b = _make_api_user("user_raport_b")

    # Create a report owned by user_a
    report_a = baker.make(RaportSlotowUczelnia, owner=user_a)
    # Create a report owned by user_b (should not appear for user_a)
    baker.make(RaportSlotowUczelnia, owner=user_b)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=_basic_auth(user_a.username, pw_a))

    url = reverse("api_v1:raport_slotow_uczelnia-list")
    response = client.get(url)

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    # The only visible report must be user_a's own report
    assert str(report_a.pk) in data["results"][0]["id"]


@pytest.mark.django_db
def test_raport_slotow_uczelnia_other_user_report_not_visible():
    """User B cannot see user A's report — owner isolation is enforced."""
    user_a, pw_a = _make_api_user("user_raport_c")
    user_b, pw_b = _make_api_user("user_raport_d")

    baker.make(RaportSlotowUczelnia, owner=user_a)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=_basic_auth(user_b.username, pw_b))

    url = reverse("api_v1:raport_slotow_uczelnia-list")
    response = client.get(url)

    assert response.status_code == 200
    assert response.json()["count"] == 0


def _basic_auth(username, password):
    import base64

    credentials = f"{username}:{password}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"
