import os

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from liveops.testing import MockProgress

from bpp.const import GR_WPROWADZANIE_DANYCH
from import_list_if.models import ImportListIf


@pytest.fixture
def testdata_xlsx_path():
    return os.path.join(os.path.dirname(__file__), "testdata1.xlsx")


def _user_w_grupie(django_user_model, username):
    user = django_user_model.objects.create_user(username=username, password="x")
    grupa, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(grupa)
    return user


def _upload(path):
    with open(path, "rb") as f:
        return SimpleUploadedFile("testdata1.xlsx", f.read())


def test_ListaImportowView_link(admin_app):
    page = admin_app.get(reverse("import_list_if:index"))
    page = page.click("pobierz plik wzorcowy")
    assert page.status_code == 200


def test_NowyImportView_link(admin_app):
    page = admin_app.get(reverse("import_list_if:new"))
    page = page.click("pobierz plik wzorcowy")
    assert page.status_code == 200


@pytest.mark.django_db
def test_create_przekierowuje_na_live_i_zapisuje_wiersze(
    client, django_user_model, testdata_xlsx_path
):
    user = _user_w_grupie(django_user_model, "creator")
    client.force_login(user)

    resp = client.post(
        reverse("import_list_if:new"),
        {"plik_xls": _upload(testdata_xlsx_path), "rok": 2020},
    )

    assert resp.status_code == 302
    op = ImportListIf.objects.get(owner=user)
    assert resp.url == op.get_absolute_url()
    assert "/live/import_list_if.importlistif/" in resp.url
    # RUNNER=eager (settings/test): run() wykonał się synchronicznie.
    assert op.importlistifrow_set.count() == 4


@pytest.mark.django_db
def test_create_wymaga_grupy_bez_side_effectu(
    client, django_user_model, testdata_xlsx_path
):
    user = django_user_model.objects.create_user(username="nogroup", password="x")
    client.force_login(user)

    resp = client.post(
        reverse("import_list_if:new"),
        {"plik_xls": _upload(testdata_xlsx_path), "rok": 2020},
    )

    # Braces GroupRequiredMixin (raise_exception=False) → redirect_to_login,
    # a NIE 403. Asertujemy też brak side-effectu: import nie powstał.
    assert resp.status_code == 302
    assert "login" in resp.url
    assert not ImportListIf.objects.filter(owner=user).exists()


@pytest.mark.django_db
def test_results_view_renderuje_wiersze_owner_scoped(
    client, django_user_model, testdata_xlsx_path
):
    owner = _user_w_grupie(django_user_model, "owner")
    op = ImportListIf(owner=owner, rok=2020)
    op.plik_xls = _upload(testdata_xlsx_path)
    op.save()
    op.run(MockProgress(op))

    url = reverse("import_list_if:importlistif-results", args=[op.pk])

    client.force_login(owner)
    resp = client.get(url)
    assert resp.status_code == 200
    assert op.importlistifrow_set.count() == 4

    # Cudzy użytkownik (też w grupie) nie widzi importu → Http404.
    inny = _user_w_grupie(django_user_model, "inny")
    client.force_login(inny)
    resp = client.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_results_view_nieistniejacy_pk_daje_404(client, django_user_model):
    """Nieistniejący pk rodzica → 404 (nie 500). Parytet z get_object_or_404
    we wzorcu import_pracownikow."""
    from uuid import uuid4

    owner = _user_w_grupie(django_user_model, "owner")
    client.force_login(owner)
    url = reverse("import_list_if:importlistif-results", args=[uuid4()])
    resp = client.get(url)
    assert resp.status_code == 404
