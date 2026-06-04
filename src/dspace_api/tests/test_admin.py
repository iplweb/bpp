import json
from unittest import mock

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from model_bakery import baker


@pytest.fixture
def fernet_key(settings):
    from cryptography.fernet import Fernet

    settings.DSPACE_CREDENTIALS_KEY = Fernet.generate_key().decode()


@pytest.fixture
def mapowanie_admin():
    from dspace_api.admin import Mapowanie_DSpaceAdmin
    from dspace_api.models import Mapowanie_DSpace

    return Mapowanie_DSpaceAdmin(Mapowanie_DSpace, AdminSite())


# --- Feature A: domyślna uczelnia ------------------------------------------


@pytest.mark.django_db
def test_initial_data_jedna_uczelnia_jest_domyslna(mapowanie_admin):
    u = baker.make("bpp.Uczelnia")
    req = RequestFactory().get("/admin/dspace_api/mapowanie_dspace/add/")
    data = mapowanie_admin.get_changeform_initial_data(req)
    assert data["uczelnia"] == u.pk


@pytest.mark.django_db
def test_initial_data_wiele_uczelni_uzywa_get_for_request(mapowanie_admin):
    u1 = baker.make("bpp.Uczelnia")
    u2 = baker.make("bpp.Uczelnia")
    req = RequestFactory().get("/admin/dspace_api/mapowanie_dspace/add/")
    # bez request._uczelnia get_for_request spada do get_default() = pierwsza
    req._uczelnia = u2
    data = mapowanie_admin.get_changeform_initial_data(req)
    assert data["uczelnia"] == u2.pk
    assert u1.pk != u2.pk


@pytest.mark.django_db
def test_initial_data_brak_uczelni_nie_wybucha(mapowanie_admin):
    req = RequestFactory().get("/admin/dspace_api/mapowanie_dspace/add/")
    data = mapowanie_admin.get_changeform_initial_data(req)
    assert "uczelnia" not in data


# --- Feature B: endpoint listy kolekcji ------------------------------------


@pytest.mark.django_db
def test_collections_endpoint_zwraca_liste(mapowanie_admin, fernet_key):
    u = baker.make("bpp.Uczelnia")
    u.dspace_api_endpoint = "https://repo/server/api"
    u.save()
    req = RequestFactory().get("/collections/", {"uczelnia": u.pk})

    with mock.patch("dspace_api.client.DSpaceClient") as ClientCls:
        ClientCls.return_value.fetch_collections.return_value = [
            {"uuid": "u1", "name": "Artykuły"}
        ]
        resp = mapowanie_admin.collections_json_view(req)

    assert resp.status_code == 200
    assert json.loads(resp.content)["collections"] == [
        {"uuid": "u1", "name": "Artykuły"}
    ]


@pytest.mark.django_db
def test_collections_endpoint_blad_zwraca_error_i_200(mapowanie_admin, fernet_key):
    u = baker.make("bpp.Uczelnia")
    u.dspace_api_endpoint = "https://repo/server/api"
    u.save()
    req = RequestFactory().get("/collections/", {"uczelnia": u.pk})

    with mock.patch("dspace_api.client.DSpaceClient") as ClientCls:
        ClientCls.return_value.fetch_collections.side_effect = RuntimeError("timeout")
        resp = mapowanie_admin.collections_json_view(req)

    assert resp.status_code == 200
    data = json.loads(resp.content)
    assert data["collections"] == []
    assert "error" in data


@pytest.mark.django_db
def test_collections_endpoint_bez_konfiguracji_zwraca_error(mapowanie_admin):
    u = baker.make("bpp.Uczelnia")  # bez dspace_api_endpoint
    req = RequestFactory().get("/collections/", {"uczelnia": u.pk})
    resp = mapowanie_admin.collections_json_view(req)
    assert resp.status_code == 200
    data = json.loads(resp.content)
    assert data["collections"] == []
    assert "error" in data


@pytest.mark.django_db
def test_collections_endpoint_bez_parametru_uczelnia(mapowanie_admin):
    req = RequestFactory().get("/collections/")
    resp = mapowanie_admin.collections_json_view(req)
    assert resp.status_code == 200
    assert json.loads(resp.content)["collections"] == []


# --- Feature C: link na change-formie rekordu (DSpaceLinkAdminMixin) --------


@pytest.mark.django_db
def test_record_admin_pokazuje_link_gdy_wyslano(admin_client, fernet_key):
    from django.urls import reverse

    from dspace_api.models import SentToDSpace

    u = baker.make("bpp.Uczelnia")
    u.dspace_api_endpoint = "https://repo.example/server/api"
    u.save()
    rec = baker.make("bpp.Patent", tytul_oryginalny="Wynalazek")
    SentToDSpace.objects.create_or_update_before_upload(rec, u, {"x": 1})
    SentToDSpace.objects.mark_as_successful(rec, u, dspace_handle="11089/777")

    resp = admin_client.get(reverse("admin:bpp_patent_change", args=[rec.pk]))
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "https://repo.example/handle/11089/777" in content
    assert "Repozytorium DSpace" in content


@pytest.mark.django_db
def test_record_admin_bez_linku_gdy_niewyslano(admin_client):
    from django.urls import reverse

    rec = baker.make("bpp.Patent", tytul_oryginalny="Wynalazek")
    resp = admin_client.get(reverse("admin:bpp_patent_change", args=[rec.pk]))
    assert resp.status_code == 200
    assert "Repozytorium DSpace" not in resp.content.decode()
