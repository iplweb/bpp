"""Helpers shared across pbn_wysylka_oswiadczen test modules."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from bpp.const import GR_WPROWADZANIE_DANYCH

User = get_user_model()


def create_user_with_group():
    """Helper to create user with GR_WPROWADZANIE_DANYCH group."""
    user = User.objects.create_user("testuser", password="testpass")
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(group)
    return user
