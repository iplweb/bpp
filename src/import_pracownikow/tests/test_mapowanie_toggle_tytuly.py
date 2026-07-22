"""Toggle ``tworz_brakujace_tytuly`` w ekranie mapowania (T3.6)."""

from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from import_pracownikow.forms import MapowanieForm
from import_pracownikow.models import ImportPracownikow

_PATCH_RUN = patch.object(ImportPracownikow, "run", lambda self, p: None)


def _upload_csv(admin_user):
    csv = b"Nazwisko;Imie;Jedn org\nKowalski;Jan;Katedra\n"
    imp = ImportPracownikow(owner=admin_user, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls = SimpleUploadedFile("p.csv", csv)
    imp.save()
    return imp


def test_form_ma_pole_tworz_brakujace_tytuly():
    f = MapowanieForm(naglowki=["nazwisko"])
    assert "tworz_brakujace_tytuly" in f.fields
    assert f.fields["tworz_brakujace_tytuly"].initial is True


@pytest.mark.django_db
def test_post_odznaczone_zapisuje_false(admin_client, admin_user):
    imp = _upload_csv(admin_user)
    url = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    dane = {
        "kol__nazwisko": "nazwisko",
        "kol__imie": "imię",
        "kol__jedn_org": "nazwa_jednostki",
        "zapisz_profil": False,
        "nazwa_profilu": "",
        # tworz_brakujace_tytuly NIEobecne → BooleanField=False (odznaczone)
    }
    with _PATCH_RUN:
        resp = admin_client.post(url, dane)
    assert resp.status_code == 302
    imp.refresh_from_db()
    assert imp.tworz_brakujace_tytuly is False


@pytest.mark.django_db
def test_post_zaznaczone_zapisuje_true(admin_client, admin_user):
    imp = _upload_csv(admin_user)
    # domyślnie True — odznaczmy najpierw, żeby test faktycznie coś sprawdzał
    imp.tworz_brakujace_tytuly = False
    imp.save(update_fields=["tworz_brakujace_tytuly"])
    url = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    dane = {
        "kol__nazwisko": "nazwisko",
        "kol__imie": "imię",
        "kol__jedn_org": "nazwa_jednostki",
        "zapisz_profil": False,
        "nazwa_profilu": "",
        "tworz_brakujace_tytuly": "on",
    }
    with _PATCH_RUN:
        resp = admin_client.post(url, dane)
    assert resp.status_code == 302
    imp.refresh_from_db()
    assert imp.tworz_brakujace_tytuly is True
