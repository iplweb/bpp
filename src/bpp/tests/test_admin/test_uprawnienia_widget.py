"""Edycja uprawnień użytkownika/grupy w adminie — sam widget Django.

Dawniej ``django-tabular-permissions`` dokładał pod dwiema listami
``filter_horizontal`` rozbudowaną tabelkę uprawnień (``id="tabular_permissions"``).
Nikt jej nie używał, więc pakiet usunięto; zostaje standardowy widget Django.
"""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse


@pytest.mark.django_db
def test_edycja_uzytkownika_bez_tabelki_uprawnien(admin_client, admin_user):
    res = admin_client.get(reverse("admin:bpp_bppuser_change", args=(admin_user.pk,)))
    assert res.status_code == 200
    content = res.content.decode()
    assert 'id="tabular_permissions"' not in content
    assert 'name="user_permissions"' in content
    assert "selectfilter" in content


@pytest.mark.django_db
def test_edycja_grupy_bez_tabelki_uprawnien(admin_client):
    grupa = Group.objects.create(name="testowa")
    res = admin_client.get(reverse("admin:auth_group_change", args=(grupa.pk,)))
    assert res.status_code == 200
    content = res.content.decode()
    assert 'id="tabular_permissions"' not in content
    assert 'name="permissions"' in content
