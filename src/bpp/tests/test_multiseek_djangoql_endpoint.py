import json

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import translation
from model_bakery import baker
from multiseek.logic import CONTAINS

from bpp.const import GR_WPROWADZANIE_DANYCH


@pytest.fixture
def uprawniony(client):
    u = baker.make("bpp.BppUser", is_superuser=True, is_staff=True)
    client.force_login(u)
    return u


@pytest.mark.django_db
def test_endpoint_requires_permission(client):
    u = baker.make("bpp.BppUser", is_superuser=False, is_staff=False)
    client.force_login(u)
    resp = client.post(reverse("multiseek-do-djangoql"), {"json": "{}"})
    assert resp.status_code == 403


@pytest.mark.django_db
def test_endpoint_happy_path(client, uprawniony):
    # Frontend serializuje operatory pod aktywnym (polskim) jezykiem strony,
    # a request przechodzi przez LocaleMiddleware (LANGUAGE_CODE="pl"), wiec
    # str(CONTAINS) w payloadzie musi byc rozwiniete pod tym samym jezykiem
    # co mapa operatorow budowana po stronie endpointu — inaczej operator
    # bylby nieprzekladalny.
    with translation.override(settings.LANGUAGE_CODE):
        operator = str(CONTAINS)
    form = {
        "form_data": [
            None,
            {"field": "Tytuł pracy", "operator": operator,
             "value": "covid", "prev_op": None},
        ],
        "ordering": {},
        "report_type": "0",
    }
    resp = client.post(
        reverse("multiseek-do-djangoql"), {"json": json.dumps(form)}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == 'tytul_oryginalny ~ "covid"'
    assert data["warnings"] == []
    assert "model=rekord" in data["editor_url"]


@pytest.mark.django_db
def test_endpoint_bad_json(client, uprawniony):
    resp = client.post(
        reverse("multiseek-do-djangoql"), {"json": "to nie jest json"}
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_endpoint_staff_in_group_allowed(client):
    from django.contrib.auth.models import Group

    u = baker.make("bpp.BppUser", is_superuser=False, is_staff=True)
    grp, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    u.groups.add(grp)
    client.force_login(u)
    resp = client.post(reverse("multiseek-do-djangoql"), {"json": "{}"})
    assert resp.status_code == 200


@pytest.mark.django_db
def test_endpoint_surfaces_warnings(client, uprawniony):
    with translation.override(settings.LANGUAGE_CODE):
        operator = str(CONTAINS)
    form = {
        "form_data": [
            None,
            {"field": "Nie ma pola", "operator": operator,
             "value": "x", "prev_op": None},
        ],
        "ordering": {},
    }
    resp = client.post(
        reverse("multiseek-do-djangoql"), {"json": json.dumps(form)}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == ""
    assert data["warnings"]  # co najmniej jedno ostrzeżenie
