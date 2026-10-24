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
def test_collections_endpoint_zwraca_liste(mapowanie_admin, fernet_key, admin_user):
    u = baker.make("bpp.Uczelnia")
    u.dspace_api_endpoint = "https://repo/server/api"
    u.save()
    req = RequestFactory().get("/collections/", {"uczelnia": u.pk})
    req.user = admin_user

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
def test_collections_endpoint_blad_zwraca_error_i_200(
    mapowanie_admin, fernet_key, admin_user
):
    u = baker.make("bpp.Uczelnia")
    u.dspace_api_endpoint = "https://repo/server/api"
    u.save()
    req = RequestFactory().get("/collections/", {"uczelnia": u.pk})
    req.user = admin_user

    with mock.patch("dspace_api.client.DSpaceClient") as ClientCls:
        ClientCls.return_value.fetch_collections.side_effect = RuntimeError("timeout")
        resp = mapowanie_admin.collections_json_view(req)

    assert resp.status_code == 200
    data = json.loads(resp.content)
    assert data["collections"] == []
    assert "error" in data


@pytest.mark.django_db
def test_collections_endpoint_bez_konfiguracji_zwraca_error(
    mapowanie_admin, admin_user
):
    u = baker.make("bpp.Uczelnia")  # bez dspace_api_endpoint
    req = RequestFactory().get("/collections/", {"uczelnia": u.pk})
    req.user = admin_user
    resp = mapowanie_admin.collections_json_view(req)
    assert resp.status_code == 200
    data = json.loads(resp.content)
    assert data["collections"] == []
    assert "error" in data


@pytest.mark.django_db
def test_collections_endpoint_bez_parametru_uczelnia(mapowanie_admin, admin_user):
    req = RequestFactory().get("/collections/")
    req.user = admin_user
    resp = mapowanie_admin.collections_json_view(req)
    assert resp.status_code == 200
    assert json.loads(resp.content)["collections"] == []


def _staff_w_grupie_dspace(username, *uczelnie):
    from django.contrib.auth.models import Group

    from bpp.const import GR_EKSPORT_DSPACE
    from bpp.models import BppUser

    user = BppUser.objects.create_user(
        username=username, password="test12345", is_staff=True
    )
    user.groups.add(Group.objects.get_or_create(name=GR_EKSPORT_DSPACE)[0])
    for u in uczelnie:
        user.accessible_uczelnie.add(u)
    return user


def _staff_z_uprawnieniami(username, *codenames):
    from django.contrib.auth.models import Permission

    from bpp.models import BppUser

    user = BppUser.objects.create_user(
        username=username, password="test12345", is_staff=True
    )
    for codename in codenames:
        user.user_permissions.add(
            Permission.objects.get(codename=codename, content_type__app_label="bpp")
        )
    return user


def _uczelnia_z_dspace():
    u = baker.make("bpp.Uczelnia")
    u.dspace_api_endpoint = "https://repo/server/api"
    u.save()
    return u


@pytest.mark.django_db
@pytest.mark.parametrize("codenames", [(), ("change_uczelnia", "view_uczelnia")])
def test_collections_endpoint_staff_bez_grupy_403(
    mapowanie_admin, fernet_key, codenames
):
    u = _uczelnia_z_dspace()
    user = _staff_z_uprawnieniami("staff", *codenames)
    req = RequestFactory().get("/collections/", {"uczelnia": u.pk})
    req.user = user

    with mock.patch("dspace_api.client.DSpaceClient") as ClientCls:
        resp = mapowanie_admin.collections_json_view(req)

    assert resp.status_code == 403
    ClientCls.assert_not_called()


@pytest.mark.django_db
def test_collections_endpoint_uczelnia_spoza_zakresu_404(mapowanie_admin, fernet_key):
    uczelnia_a = _uczelnia_z_dspace()
    uczelnia_b = _uczelnia_z_dspace()
    user = _staff_w_grupie_dspace("staff_a", uczelnia_a)
    req = RequestFactory().get("/collections/", {"uczelnia": uczelnia_b.pk})
    req.user = user

    with mock.patch("dspace_api.client.DSpaceClient") as ClientCls:
        resp = mapowanie_admin.collections_json_view(req)

    assert resp.status_code == 404
    ClientCls.assert_not_called()


@pytest.mark.django_db
def test_collections_endpoint_nieistniejaca_uczelnia_404(mapowanie_admin, admin_user):
    for wartosc in ["999999", "abc"]:
        req = RequestFactory().get("/collections/", {"uczelnia": wartosc})
        req.user = admin_user
        with mock.patch("dspace_api.client.DSpaceClient") as ClientCls:
            resp = mapowanie_admin.collections_json_view(req)
        assert resp.status_code == 404
        ClientCls.assert_not_called()


@pytest.mark.django_db
def test_collections_endpoint_uczelnia_w_zakresie_wola_klienta(
    mapowanie_admin, fernet_key
):
    uczelnia_a = _uczelnia_z_dspace()
    _uczelnia_z_dspace()
    user = _staff_w_grupie_dspace("staff_a", uczelnia_a)
    req = RequestFactory().get("/collections/", {"uczelnia": uczelnia_a.pk})
    req.user = user

    with mock.patch("dspace_api.client.DSpaceClient") as ClientCls:
        ClientCls.return_value.fetch_collections.return_value = [
            {"uuid": "u1", "name": "Artykuły"}
        ]
        resp = mapowanie_admin.collections_json_view(req)

    assert resp.status_code == 200
    ClientCls.assert_called_once_with(uczelnia_a)
    assert json.loads(resp.content)["collections"] == [
        {"uuid": "u1", "name": "Artykuły"}
    ]


@pytest.mark.django_db
def test_collections_endpoint_przez_url_staff_bez_uprawnien(client, fernet_key):
    from django.urls import reverse

    from bpp.models import BppUser

    u = _uczelnia_z_dspace()
    user = BppUser.objects.create_user(
        username="staff", password="test12345", is_staff=True
    )
    client.force_login(user)

    with mock.patch("dspace_api.client.DSpaceClient") as ClientCls:
        resp = client.get(
            reverse("admin:dspace_api_mapowanie_dspace_collections"),
            {"uczelnia": u.pk},
        )

    assert resp.status_code == 403
    ClientCls.assert_not_called()


@pytest.mark.django_db
def test_collections_endpoint_przez_url_superuser(admin_client, fernet_key):
    from django.urls import reverse

    u = _uczelnia_z_dspace()
    with mock.patch("dspace_api.client.DSpaceClient") as ClientCls:
        ClientCls.return_value.fetch_collections.return_value = []
        resp = admin_client.get(
            reverse("admin:dspace_api_mapowanie_dspace_collections"),
            {"uczelnia": u.pk},
        )

    assert resp.status_code == 200
    ClientCls.assert_called_once_with(u)


@pytest.mark.django_db
def test_collections_endpoint_przez_url_staff_w_grupie(client, fernet_key):
    from django.contrib.auth.models import Permission
    from django.urls import reverse

    u = _uczelnia_z_dspace()
    user = _staff_w_grupie_dspace("staff_dspace")
    user.user_permissions.add(
        Permission.objects.get(
            codename="change_mapowanie_dspace", content_type__app_label="dspace_api"
        )
    )
    client.force_login(user)

    with mock.patch("dspace_api.client.DSpaceClient") as ClientCls:
        ClientCls.return_value.fetch_collections.return_value = []
        resp = client.get(
            reverse("admin:dspace_api_mapowanie_dspace_collections"),
            {"uczelnia": u.pk},
        )

    assert resp.status_code == 200
    ClientCls.assert_called_once_with(u)


# --- Akcje „Wyślij do DSpace" — grupa eksportu + prawo change -----------------

AKCJE_DSPACE = {"wyslij_do_dspace", "wyslij_do_dspace_w_tle"}

MODELE_Z_AKCJAMI_DSPACE = [
    "wydawnictwo_ciagle",
    "wydawnictwo_zwarte",
    "praca_doktorska",
    "praca_habilitacyjna",
]


def _akcje_dla(user, model_name):
    from django.apps import apps
    from django.contrib import admin

    model = apps.get_model("bpp", model_name)
    model_admin = admin.site._registry[model]
    req = RequestFactory().get("/admin/")
    req.user = user
    return set(model_admin.get_actions(req))


@pytest.mark.parametrize("akcja", sorted(AKCJE_DSPACE))
def test_akcje_dspace_wymagaja_uprawnienia_eksportu(akcja):
    from dspace_api import actions

    assert getattr(actions, akcja).allowed_permissions == ("eksport_dspace",)


@pytest.mark.django_db
@pytest.mark.parametrize("model_name", MODELE_Z_AKCJAMI_DSPACE)
def test_akcje_dspace_widoczne_dla_grupy_z_prawem_change(model_name):
    from django.contrib.auth.models import Permission

    user = _staff_w_grupie_dspace("staff_dspace")
    user.user_permissions.add(
        *Permission.objects.filter(
            codename__in=[f"change_{model_name}", f"view_{model_name}"],
            content_type__app_label="bpp",
        )
    )
    assert AKCJE_DSPACE <= _akcje_dla(user, model_name)


@pytest.mark.django_db
@pytest.mark.parametrize("model_name", MODELE_Z_AKCJAMI_DSPACE)
def test_akcje_dspace_ukryte_dla_grupy_bez_prawa_change(model_name):
    user = _staff_w_grupie_dspace("staff_dspace")
    assert not (AKCJE_DSPACE & _akcje_dla(user, model_name))


@pytest.mark.django_db
@pytest.mark.parametrize("model_name", MODELE_Z_AKCJAMI_DSPACE)
def test_akcje_dspace_ukryte_dla_staff_bez_grupy(model_name):
    user = _staff_z_uprawnieniami(
        "staff", f"change_{model_name}", f"view_{model_name}", "change_uczelnia"
    )
    akcje = _akcje_dla(user, model_name)
    assert "ustaw_po_korekcie" in akcje
    assert not (AKCJE_DSPACE & akcje)


@pytest.mark.django_db
@pytest.mark.parametrize("model_name", MODELE_Z_AKCJAMI_DSPACE)
def test_akcje_dspace_widoczne_dla_superusera(model_name, admin_user):
    assert AKCJE_DSPACE <= _akcje_dla(admin_user, model_name)


@pytest.mark.django_db
def test_akcja_dspace_przez_post_bez_grupy_nie_wysyla(client):
    from django.urls import reverse

    rec = baker.make("bpp.Wydawnictwo_Ciagle")
    user = _staff_z_uprawnieniami(
        "staff", "change_wydawnictwo_ciagle", "view_wydawnictwo_ciagle"
    )
    client.force_login(user)

    with mock.patch("dspace_api.actions.eksportuj_rekord") as eksport:
        client.post(
            reverse("admin:bpp_wydawnictwo_ciagle_changelist"),
            {"action": "wyslij_do_dspace", "_selected_action": [rec.pk]},
        )

    eksport.assert_not_called()


@pytest.mark.django_db
def test_odtworz_grupy_tworzy_grupe_eksportu_dspace():
    from django.contrib.auth.models import Group

    from bpp.const import GR_EKSPORT_DSPACE
    from bpp.system import odtworz_grupy

    Group.objects.filter(name=GR_EKSPORT_DSPACE).delete()
    odtworz_grupy()

    grupa = Group.objects.get(name=GR_EKSPORT_DSPACE)
    assert set(
        grupa.permissions.values_list("content_type__app_label", "codename")
    ) == {
        ("dspace_api", f"{akcja}_{model}")
        for akcja in ("add", "change", "delete", "view")
        for model in ("mapowanie_dspace", "senttodspace")
    }


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
