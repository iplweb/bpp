"""Bezpieczniki rozmiaru pliku importu pracowników — widoki pokazują
komunikat zamiast błędu 500."""

import pytest
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from import_common.tests._pliki_limity import maly_limit_pliku
from import_pracownikow.models import ImportPracownikow

CSV = b"Nazwisko;Imie;Jedn org\nKowalski;Jan;Katedra\n" * 20


def _import(admin_user, stan=ImportPracownikow.STAN_UTWORZONY):
    imp = ImportPracownikow(owner=admin_user, stan=stan)
    imp.plik_xls = SimpleUploadedFile("p.csv", CSV)
    imp.save()
    return imp


def _komunikaty(resp):
    return [str(m) for m in get_messages(resp.wsgi_request)]


@pytest.mark.django_db
def test_mapowanie_za_duzy_plik_komunikat(admin_client, admin_user, monkeypatch):
    imp = _import(admin_user)
    maly_limit_pliku(monkeypatch)
    url = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    assert resp.status_code == 302
    assert any("limit" in m for m in _komunikaty(resp))


@pytest.mark.django_db
def test_mapowanie_poprawny_plik(admin_client, admin_user):
    imp = _import(admin_user)
    url = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    assert resp.status_code == 200
    assert b"kol__nazwisko" in resp.content


@pytest.mark.django_db
def test_restart_analizy_za_duzy_plik_komunikat(admin_client, admin_user, monkeypatch):
    imp = _import(admin_user, stan=ImportPracownikow.STAN_PRZEANALIZOWANY)
    maly_limit_pliku(monkeypatch)
    url = reverse("import_pracownikow:restart-analiza", kwargs={"pk": imp.pk})
    resp = admin_client.post(url)
    assert resp.status_code == 302
    assert any("limit" in m for m in _komunikaty(resp))
