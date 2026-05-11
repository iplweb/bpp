"""Smoke test for the django-formdefaults popup buttons rendered next to
forms. Three roles are exercised:

- anonymous: no buttons
- regular logged-in user: only "My defaults"
- is_staff: both "My defaults" and "System defaults"

The view used is ``raport_slotow:index`` (already wired up via
``FormDefaultsMixin``) but the assertions are about the template-tag
output, so any other auth-required form view would do.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from bpp.models import OpcjaWyswietlaniaField

USER_PASSWORD = "password"  # noqa: S105


@pytest.fixture
def _uczelnia_pokazuj(uczelnia):
    uczelnia.pokazuj_raport_slotow_autor = OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
    uczelnia.save()
    return uczelnia


@pytest.fixture
def staff_user(db):
    return get_user_model().objects.create_user(
        username="fd_staff",
        password=USER_PASSWORD,
        email="staff@example.com",
        is_staff=True,
    )


@pytest.fixture
def regular_user(db):
    return get_user_model().objects.create_user(
        username="fd_regular",
        password=USER_PASSWORD,
        email="regular@example.com",
        is_staff=False,
    )


def _login(user):
    client = Client()
    assert client.login(username=user.username, password=USER_PASSWORD)
    return client


def test_anonymous_sees_no_formdefaults_buttons(_uczelnia_pokazuj):
    res = Client().get(reverse("raport_slotow:index"))
    # Anon may be redirected to login; either way the buttons must not be
    # rendered in the (possibly redirected) HTML.
    assert b"fd-edit-btn" not in res.content


def test_regular_user_sees_only_personal_button(_uczelnia_pokazuj, regular_user):
    res = _login(regular_user).get(reverse("raport_slotow:index"))
    assert res.status_code == 200
    assert b"fd-edit-btn" in res.content
    assert b"fd-edit-btn-system" not in res.content


def test_staff_user_sees_both_buttons(_uczelnia_pokazuj, staff_user):
    res = _login(staff_user).get(reverse("raport_slotow:index"))
    assert res.status_code == 200
    assert b"fd-edit-btn" in res.content
    assert b"fd-edit-btn-system" in res.content
