from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from import_pracownikow.forms import MapowanieForm
from import_pracownikow.mapping import POLE_POMIN
from import_pracownikow.models import ImportPracownikow, ProfilMapowania


def _dane(naglowki, mapowanie, zapisz=False, nazwa=""):
    d = {f"kol__{h}": mapowanie.get(h, POLE_POMIN) for h in naglowki}
    d["zapisz_profil"] = zapisz
    d["nazwa_profilu"] = nazwa
    return d


# W testach LIVEOPS.RUNNER="eager" (settings/test.py) — enqueue() wykonuje run()
# SYNCHRONICZNIE. W testach jednostkowych widoku patchujemy run, żeby POST nie
# odpalał analizy (brak autora/jednostki w DB → wyjątek; poza tym testujemy
# zapis mapowania, nie analizę).
_PATCH_RUN = patch.object(ImportPracownikow, "run", lambda self, p: None)


def _upload_csv(admin_user):
    csv = b"Nazwisko;Imie;Jedn org\nKowalski;Jan;Katedra\n"
    imp = ImportPracownikow(owner=admin_user, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls = SimpleUploadedFile("p.csv", csv)
    imp.save()
    return imp


def test_mapowanieform_buduje_pola_z_naglowkow():
    f = MapowanieForm(naglowki=["nazwisko", "imię", "jedn_org"])
    assert "kol__nazwisko" in f.fields
    assert "kol__jedn_org" in f.fields
    # auto-propozycja jako initial
    assert f.fields["kol__jedn_org"].initial == "nazwa_jednostki"


def test_mapowanieform_valid_zwraca_mapowanie():
    naglowki = ["nazwisko", "imię", "jedn_org"]
    f = MapowanieForm(
        naglowki=naglowki,
        data=_dane(
            naglowki,
            {"nazwisko": "nazwisko", "imię": "imię", "jedn_org": "nazwa_jednostki"},
        ),
    )
    assert f.is_valid(), f.errors
    assert f.mapowanie() == {
        "nazwisko": "nazwisko",
        "imię": "imię",
        "jedn_org": "nazwa_jednostki",
    }


def test_mapowanieform_invalid_bez_jednostki():
    naglowki = ["nazwisko", "imię"]
    f = MapowanieForm(
        naglowki=naglowki,
        data=_dane(naglowki, {"nazwisko": "nazwisko", "imię": "imię"}),
    )
    assert not f.is_valid()


@pytest.mark.django_db
def test_mapowanie_get_pokazuje_kolumny(admin_client, admin_user):
    imp = _upload_csv(admin_user)
    url = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    assert resp.status_code == 200
    assert b"kol__nazwisko" in resp.content
    assert b"kol__jedn_org" in resp.content


@pytest.mark.django_db
def test_mapowanie_post_zapisuje_i_przechodzi_w_zmapowany(admin_client, admin_user):
    imp = _upload_csv(admin_user)
    url = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    data = {
        "kol__nazwisko": "nazwisko",
        "kol__imie": "imię",
        "kol__jedn_org": "nazwa_jednostki",
        "zapisz_profil": False,
        "nazwa_profilu": "",
    }
    with _PATCH_RUN:
        resp = admin_client.post(url, data)
    assert resp.status_code == 302  # redirect na stronę live
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZMAPOWANY
    assert imp.mapowanie_kolumn["jedn_org"] == "nazwa_jednostki"


@pytest.mark.django_db
def test_mapowanie_post_zapisuje_profil(admin_client, admin_user):
    imp = _upload_csv(admin_user)
    url = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    data = {
        "kol__nazwisko": "nazwisko",
        "kol__imie": "imię",
        "kol__jedn_org": "nazwa_jednostki",
        "zapisz_profil": True,
        "nazwa_profilu": "Mój profil",
    }
    with _PATCH_RUN:
        admin_client.post(url, data)
    assert ProfilMapowania.objects.filter(nazwa="Mój profil").exists()


@pytest.mark.django_db
def test_mapowanie_post_na_zintegrowanym_nie_kasuje_wierszy(admin_client, admin_user):
    # gate stanu (F4): import zintegrowany nie jest mapowalny — POST NIE może
    # skasować wierszy-audytu (log_zmian) ani odpalić ponownej analizy
    imp = _upload_csv(admin_user)
    imp.stan = ImportPracownikow.STAN_ZINTEGROWANY
    imp.save(update_fields=["stan"])
    from model_bakery import baker

    baker.make("import_pracownikow.ImportPracownikowRow", parent=imp)
    url = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    with _PATCH_RUN:
        resp = admin_client.post(
            url,
            {
                "kol__nazwisko": "nazwisko",
                "kol__imie": "imię",
                "kol__jedn_org": "nazwa_jednostki",
                "zapisz_profil": False,
                "nazwa_profilu": "",
            },
        )
    assert resp.status_code == 302
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZINTEGROWANY  # niezmieniony
    assert imp.importpracownikowrow_set.count() == 1  # audyt zachowany
