"""
Tests for Phase 3 views.

Covers: create form GET/POST, live page rendering (channel + token attributes),
finished-op inline result, cancel POST/GET, anonymous redirect, cross-user 404.
"""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from tests.models import DemoOp

User = get_user_model()


# ------------------------------------------------------------------ #
# Fixtures                                                             #
# ------------------------------------------------------------------ #


@pytest.fixture
def user(db):
    return User.objects.create_user(username="testuser", password="pass")


@pytest.fixture
def other_user(db):
    return User.objects.create_user(username="otheruser", password="pass")


@pytest.fixture
def auth_client(user):
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def anon_client():
    return Client()


@pytest.fixture
def demo_op(user):
    return DemoOp.objects.create(owner=user)


@pytest.fixture
def finished_op(user):
    from django.utils import timezone

    return DemoOp.objects.create(
        owner=user,
        finished_on=timezone.now(),
        finished_successfully=True,
        result_context={"message": "done"},
    )


# ------------------------------------------------------------------ #
# Create view                                                          #
# ------------------------------------------------------------------ #


@pytest.mark.django_db
def test_create_get_returns_200(auth_client):
    response = auth_client.get("/new/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_create_post_creates_op_owner_set_and_redirects(auth_client, user):
    response = auth_client.post("/new/", data={})
    assert response.status_code == 302
    op = DemoOp.objects.filter(owner=user).first()
    assert op is not None
    assert op.owner == user
    # Eager runner ran the op synchronously; terminal state committed
    assert op.finished_on is not None


@pytest.mark.django_db
def test_create_post_redirect_points_to_live_page(auth_client, user):
    response = auth_client.post("/new/", data={})
    op = DemoOp.objects.filter(owner=user).first()
    assert response["Location"] == f"/{op.pk}/"


# ------------------------------------------------------------------ #
# Live page                                                            #
# ------------------------------------------------------------------ #


@pytest.mark.django_db
def test_live_page_returns_200(auth_client, demo_op):
    response = auth_client.get(f"/{demo_op.pk}/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_live_page_has_channel_attribute(auth_client, demo_op):
    response = auth_client.get(f"/{demo_op.pk}/")
    content = response.content.decode()
    assert f'data-liveop-channel="liveop.{demo_op.pk}"' in content


@pytest.mark.django_db
def test_live_page_has_non_empty_token(auth_client, demo_op):
    response = auth_client.get(f"/{demo_op.pk}/")
    content = response.content.decode()
    assert 'data-liveop-token="' in content
    # Token must be a non-trivial signed value
    token = response.context["object"].subscription_token
    assert len(token) > 20


@pytest.mark.django_db
def test_live_page_contains_region_divs(auth_client, demo_op):
    response = auth_client.get(f"/{demo_op.pk}/")
    content = response.content.decode()
    for region in ("op-status", "op-progress", "op-log", "op-result"):
        assert region in content, f"region {region!r} missing from live page"


@pytest.mark.django_db
def test_finished_op_renders_result_inline(auth_client, finished_op):
    response = auth_client.get(f"/{finished_op.pk}/")
    assert response.status_code == 200
    content = response.content.decode()
    # op-result div present and contains the result data
    assert "op-result" in content
    assert "message=done" in content


# ------------------------------------------------------------------ #
# Cancel view                                                          #
# ------------------------------------------------------------------ #


@pytest.mark.django_db
def test_cancel_post_sets_flag(auth_client, demo_op):
    response = auth_client.post(f"/{demo_op.pk}/cancel/")
    assert response.status_code == 302
    demo_op.refresh_from_db()
    assert demo_op.cancel_requested is True


@pytest.mark.django_db
def test_cancel_get_returns_405(auth_client, demo_op):
    response = auth_client.get(f"/{demo_op.pk}/cancel/")
    assert response.status_code == 405


# ------------------------------------------------------------------ #
# Access control                                                       #
# ------------------------------------------------------------------ #


@pytest.mark.django_db
def test_anonymous_user_redirected_to_login(anon_client, demo_op):
    response = anon_client.get(f"/{demo_op.pk}/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_other_user_cannot_see_op(other_user, demo_op):
    c = Client()
    c.force_login(other_user)
    response = c.get(f"/{demo_op.pk}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_other_user_cannot_cancel_op(other_user, demo_op):
    c = Client()
    c.force_login(other_user)
    response = c.post(f"/{demo_op.pk}/cancel/")
    assert response.status_code == 404
