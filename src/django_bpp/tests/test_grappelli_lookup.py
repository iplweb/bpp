import json

import pytest
from django.contrib.auth.models import Permission
from django.urls import resolve, reverse
from model_bakery import baker

from bpp.models import BppUser, Jezyk
from django_bpp.grappelli_lookup import (
    BppAutocompleteLookup,
    BppM2MLookup,
    BppRelatedLookup,
    klucz_filtra_dozwolony,
)

RELATED_URL = "/grappelli/lookup/related/"
M2M_URL = "/grappelli/lookup/m2m/"
AUTOCOMPLETE_URL = "/grappelli/lookup/autocomplete/"


@pytest.fixture
def staff_client(client, db):
    user = baker.make(BppUser, is_staff=True, is_active=True, is_superuser=False)
    client.force_login(user)
    client.user = user
    return client


def test_trasy_wskazuja_na_widoki_bpp():
    assert resolve(RELATED_URL).func.view_class is BppRelatedLookup
    assert resolve(M2M_URL).func.view_class is BppM2MLookup
    assert resolve(AUTOCOMPLETE_URL).func.view_class is BppAutocompleteLookup
    assert reverse("grp_related_lookup") == RELATED_URL
    assert reverse("grp_m2m_lookup") == M2M_URL
    assert reverse("grp_autocomplete_lookup") == AUTOCOMPLETE_URL


@pytest.mark.django_db
@pytest.mark.parametrize("url", [RELATED_URL, M2M_URL])
def test_staff_bez_uprawnien_do_uzytkownikow(staff_client, url):
    res = staff_client.get(
        url,
        {
            "object_id": str(staff_client.user.pk),
            "app_label": "bpp",
            "model_name": "bppuser",
        },
    )
    assert res.status_code == 403


@pytest.mark.django_db
def test_staff_bez_uprawnien_autocomplete(staff_client):
    res = staff_client.get(
        AUTOCOMPLETE_URL,
        {"term": "a", "app_label": "bpp", "model_name": "bppuser"},
    )
    assert res.status_code == 403


@pytest.mark.django_db
def test_model_spoza_admina_odrzucony(admin_client):
    res = admin_client.get(
        RELATED_URL,
        {"object_id": "1", "app_label": "sessions", "model_name": "session"},
    )
    assert res.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query_string",
    [
        "password__startswith=pbkdf2",
        "user__password__startswith=x",
        "groups__name=x",
        "nazwa__regex=.*",
        "nazwa__startswith=a",
        "bppuser__username=admin",
        "zle",
    ],
)
def test_query_string_odrzucany(admin_client, query_string):
    jezyk = baker.make(Jezyk)
    res = admin_client.get(
        RELATED_URL,
        {
            "object_id": str(jezyk.pk),
            "app_label": "bpp",
            "model_name": "jezyk",
            "query_string": query_string,
        },
    )
    assert res.status_code == 403


@pytest.mark.django_db
def test_query_string_przez_relacje_do_uzytkownika_odrzucany(admin_client):
    res = admin_client.get(
        RELATED_URL,
        {
            "object_id": str(admin_client.session["_auth_user_id"]),
            "app_label": "bpp",
            "model_name": "bppuser",
            "query_string": "auth_token__key__startswith=a",
        },
    )
    assert res.status_code == 403


@pytest.mark.django_db
def test_to_field_wrazliwy_odrzucony(admin_client, admin_user):
    res = admin_client.get(
        RELATED_URL,
        {
            "object_id": str(admin_user.pk),
            "app_label": "bpp",
            "model_name": "bppuser",
            "to_field": "password",
        },
    )
    assert res.status_code == 403


@pytest.mark.django_db
def test_lookup_z_uprawnieniem_view_zwraca_etykiete(staff_client):
    staff_client.user.user_permissions.add(
        Permission.objects.get(content_type__app_label="bpp", codename="view_jezyk")
    )
    jezyk = baker.make(Jezyk, nazwa="klingoński", widoczny=True)
    res = staff_client.get(
        RELATED_URL,
        {
            "object_id": str(jezyk.pk),
            "app_label": "bpp",
            "model_name": "jezyk",
            "to_field": "id",
            # Tak grappelli przekazuje ``limit_choices_to={"widoczny": True}``
            "query_string": "widoczny=1:_to_field=id",
        },
    )
    assert res.status_code == 200
    data = json.loads(res.content)
    assert data[0]["value"] == str(jezyk.pk)
    assert "klingoński" in data[0]["label"]


@pytest.mark.django_db
def test_m2m_lookup_z_uprawnieniem_view(staff_client):
    staff_client.user.user_permissions.add(
        Permission.objects.get(content_type__app_label="bpp", codename="view_jezyk")
    )
    j1 = baker.make(Jezyk, nazwa="aaa1")
    j2 = baker.make(Jezyk, nazwa="bbb2")
    res = staff_client.get(
        M2M_URL,
        {
            "object_id": f"{j1.pk},{j2.pk}",
            "app_label": "bpp",
            "model_name": "jezyk",
        },
    )
    assert res.status_code == 200
    labels = [x["label"] for x in json.loads(res.content)]
    assert any("aaa1" in x for x in labels)
    assert any("bbb2" in x for x in labels)


@pytest.mark.django_db
def test_autocomplete_nieznany_model(admin_client):
    res = admin_client.get(
        AUTOCOMPLETE_URL,
        {"term": "a", "app_label": "bpp", "model_name": "nieistnieje"},
    )
    assert res.status_code == 200


@pytest.mark.django_db
def test_klucze_limit_choices_to_uzywane_w_bpp():
    from django.contrib.contenttypes.models import ContentType

    assert klucz_filtra_dozwolony(Jezyk, "widoczny")
    assert klucz_filtra_dozwolony(ContentType, "app_label")
    assert klucz_filtra_dozwolony(ContentType, "model__in")
    assert not klucz_filtra_dozwolony(ContentType, "model__regex")


def _raw_id_pola():
    from django.contrib import admin
    from django.contrib.admin.widgets import url_params_from_lookup_dict

    for model, model_admin in list(admin.site._registry.items()):
        admini = [(model, model_admin)] + [
            (inline.model, inline) for inline in model_admin.inlines
        ]
        for m, ma in admini:
            for nazwa in getattr(ma, "raw_id_fields", ()):
                pole = m._meta.get_field(nazwa)
                yield (
                    f"{m._meta.label}.{nazwa}",
                    pole.remote_field.model,
                    url_params_from_lookup_dict(pole.remote_field.limit_choices_to),
                )


def test_raw_id_fields_w_adminie_przechodza_walidacje():
    from django.contrib import admin

    sprawdzone = 0
    for etykieta, cel, parametry in _raw_id_pola():
        if cel not in admin.site._registry:
            # Django nie renderuje linku lookupu dla modelu spoza admina,
            # więc grappelli nie ma skąd wziąć app_label/model_name.
            continue
        for klucz in parametry:
            if klucz == "_to_field":
                continue
            assert klucz_filtra_dozwolony(cel, klucz), (etykieta, klucz)
        sprawdzone += 1
    assert sprawdzone > 0
