import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH

URL_NAME = "ewaluacja_dwudyscyplinowcy:index"


@pytest.mark.django_db
def test_anonim_przekierowany_na_logowanie(client):
    assert client.get(reverse(URL_NAME)).status_code == 302


@pytest.mark.django_db
def test_zwykly_user_dostaje_403(client):
    user = baker.make("bpp.BppUser", is_staff=False, is_superuser=False)
    client.force_login(user)
    assert client.get(reverse(URL_NAME)).status_code == 403


@pytest.mark.django_db
def test_user_powiazany_z_autorem_bez_grupy_dostaje_403(client):
    autor = baker.make("bpp.Autor")
    user = baker.make("bpp.BppUser", is_staff=False, is_superuser=False, autor=autor)
    client.force_login(user)
    assert client.get(reverse(URL_NAME)).status_code == 403


@pytest.mark.django_db
def test_redaktor_ma_dostep(client):
    user = baker.make("bpp.BppUser", is_staff=True, is_superuser=False)
    grupa, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(grupa)
    client.force_login(user)
    assert client.get(reverse(URL_NAME)).status_code == 200
