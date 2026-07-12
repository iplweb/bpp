"""Reguła „jeden arkusz = jeden import".

Plik wieloarkuszowy (np. ``Pracownicy_..._UAFM_x_MWSL.xlsx`` — dwie uczelnie
w jednym skoroszycie) jest ODRZUCANY z czytelnym błędem. Świadomie NIE
obsługujemy takich plików (ani auto-sklejenia, ani auto-podziału — arkusze to
rozłączne, nieporównywalne zbiory). Użytkownik dzieli plik na osobne pliki
(po jednym arkuszu) i importuje każdy osobno.
"""

import openpyxl
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from import_common.exceptions import BadNoOfSheetsException
from import_pracownikow.models import ImportPracownikow


def _plik_dwa_arkusze(tmp_path):
    wb = openpyxl.Workbook()
    ws0 = wb.active
    ws0.title = "UAFM"
    ws0.append(["Nazwisko", "Imię", "Stanowisko"])
    ws0.append(["Kowalski", "Jan", "Adiunkt"])
    ws1 = wb.create_sheet("MWSL")
    ws1.append(["Nazwisko", "Imię", "Stanowisko"])
    ws1.append(["Nowak", "Ewa", "Profesor"])
    p = tmp_path / "dwa_arkusze.xlsx"
    wb.save(str(p))
    return p


def _import_z_pliku(user, path):
    imp = ImportPracownikow(owner=user)
    with open(path, "rb") as f:
        imp.plik_xls = SimpleUploadedFile("dwa_arkusze.xlsx", f.read())
    imp.save()
    return imp


@pytest.mark.django_db
def test_naglowki_i_probka_odrzuca_plik_wieloarkuszowy(admin_user, tmp_path):
    imp = _import_z_pliku(admin_user, _plik_dwa_arkusze(tmp_path))
    with pytest.raises(BadNoOfSheetsException):
        imp.naglowki_i_probka()


@pytest.mark.django_db
def test_waliduj_liczbe_arkuszy_odrzuca_plik_wieloarkuszowy(admin_user, tmp_path):
    imp = _import_z_pliku(admin_user, _plik_dwa_arkusze(tmp_path))
    with pytest.raises(BadNoOfSheetsException):
        imp.waliduj_liczbe_arkuszy()


@pytest.mark.django_db
def test_restart_analiza_view_odrzuca_plik_wieloarkuszowy(
    admin_client, admin_user, tmp_path
):
    """Bezpiecznik na ścieżce restartu: RESTART istniejącego importu (np. sprzed
    tej reguły) wchodzi w analizę z pominięciem ekranu mapowania — widok
    restartu odrzuca plik wieloarkuszowy z czytelnym komunikatem, bez re-enqueue."""
    imp = _import_z_pliku(admin_user, _plik_dwa_arkusze(tmp_path))
    url = reverse("import_pracownikow:restart-analiza", kwargs={"pk": imp.pk})
    resp = admin_client.post(url, follow=True)
    assert resp.status_code == 200
    assert "więcej niż jeden arkusz" in resp.content.decode("utf-8")


@pytest.mark.django_db
def test_mapowanie_view_odrzuca_plik_wieloarkuszowy(admin_client, admin_user, tmp_path):
    """Ekran mapowania odrzuca plik wieloarkuszowy od razu — redirect na listę
    z czytelnym komunikatem, zamiast crashu w tle."""
    imp = _import_z_pliku(admin_user, _plik_dwa_arkusze(tmp_path))
    url = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    resp = admin_client.get(url, follow=True)
    assert resp.status_code == 200
    assert "więcej niż jeden arkusz" in resp.content.decode("utf-8")


@pytest.mark.django_db
def test_import_jednoarkuszowy_przechodzi(
    admin_client, admin_user, baza_importu_pracownikow, testdata_xlsx_path
):
    """Regresja: plik JEDNOARKUSZOWY nadal działa (reguła nie blokuje normalnych
    importów) — ekran mapowania renderuje kolumny."""
    from import_pracownikow.tests.conftest import import_pracownikow_factory

    imp = import_pracownikow_factory(admin_user, testdata_xlsx_path)
    url = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    assert resp.status_code == 200
