import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from import_pracownikow.models import ImportPracownikow


def _user_w_grupie(django_user_model, username="entry"):
    u = django_user_model.objects.create_user(username=username, password="pass")
    grupa, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    u.groups.add(grupa)
    return u


def _import_z_plikiem(owner, nazwa="testdata.xlsx"):
    imp = baker.make(ImportPracownikow, owner=owner)
    imp.plik_xls.save(nazwa, SimpleUploadedFile(nazwa, b"PK\x03\x04udawany"), save=True)
    return imp


@pytest.mark.django_db
def test_oryginal_pobiera_wlasciciel_z_grupa(client, django_user_model):
    u = _user_w_grupie(django_user_model)
    client.force_login(u)
    imp = _import_z_plikiem(u)
    resp = client.get(
        reverse("import_pracownikow:pobierz-oryginal", kwargs={"pk": imp.pk})
    )
    assert resp.status_code == 200
    assert "attachment" in resp["Content-Disposition"]
    assert "testdata.xlsx" in resp["Content-Disposition"]


@pytest.mark.django_db
def test_oryginal_bez_grupy_odmowa(client, django_user_model):
    u = django_user_model.objects.create_user(username="plain", password="pass")
    client.force_login(u)
    imp = _import_z_plikiem(u)
    resp = client.get(
        reverse("import_pracownikow:pobierz-oryginal", kwargs={"pk": imp.pk})
    )
    assert resp.status_code != 200  # braces GroupRequiredMixin blokuje


@pytest.mark.django_db
def test_oryginal_cudzy_import_404(client, django_user_model):
    wlasciciel = _user_w_grupie(django_user_model, "wlasciciel")
    obcy = _user_w_grupie(django_user_model, "obcy")
    imp = _import_z_plikiem(wlasciciel)
    client.force_login(obcy)
    resp = client.get(
        reverse("import_pracownikow:pobierz-oryginal", kwargs={"pk": imp.pk})
    )
    assert resp.status_code == 404


@pytest.mark.django_db
def test_oryginal_brak_pliku_404(client, django_user_model):
    u = _user_w_grupie(django_user_model)
    client.force_login(u)
    imp = baker.make(ImportPracownikow, owner=u)  # bez plik_xls
    resp = client.get(
        reverse("import_pracownikow:pobierz-oryginal", kwargs={"pk": imp.pk})
    )
    assert resp.status_code == 404
