"""Widoki importu a multi-hosted uczelnia:

- ``NowyImportView`` łapie uczelnię z requestu i utrwala na imporcie,
- ekran ``/jednostki/`` GŁOŚNO ostrzega, gdy uczelni nie da się ustalić, a są
  jednostki „do utworzenia" (zamiast cichego pominięcia).
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from model_bakery import baker

from bpp.models import Uczelnia
from import_pracownikow.models import ImportPracownikow, ImportPracownikowJednostka

BRAK = ImportPracownikowJednostka.TRYB_BRAK


def _jedyna_uczelnia():
    """Utwardza „dokładnie jedna uczelnia" (kasuje ambient-nadmiar spod xdist)."""
    u = baker.make(Uczelnia)
    Uczelnia.objects.exclude(pk=u.pk).delete()
    return u


@pytest.mark.django_db
def test_nowy_import_lapie_uczelnie_z_requestu(admin_client):
    """POST na ``/new/`` tworzy import z ustawioną ``uczelnia`` (z requestu —
    przy jednej uczelni to ona przez fallback ``get_single_uczelnia_or_none``)."""
    u = _jedyna_uczelnia()
    plik = SimpleUploadedFile(
        "wykaz.xlsx",
        b"PK\x03\x04 dummy",  # form to FileField — nie waliduje treści xlsx tutaj
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp = admin_client.post(reverse("import_pracownikow:new"), {"plik_xls": plik})
    assert resp.status_code == 302  # redirect na mapowanie
    imp = ImportPracownikow.objects.latest("pk")
    assert imp.uczelnia_id == u.pk


@pytest.mark.django_db
def test_jednostki_ostrzega_gdy_uczelnia_nieokreslona(admin_client, admin_user):
    """>1 uczelnia + import bez ustalonej uczelni + jednostka „do utworzenia" →
    ekran /jednostki/ pokazuje WIDOCZNE ostrzeżenie nad listą jednostek."""
    baker.make(Uczelnia)
    baker.make(Uczelnia)  # >1 → uczelnia_do_integracji() = None
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        uczelnia=None,
    )
    baker.make(
        ImportPracownikowJednostka,
        parent=imp,
        nazwa_zrodlowa="Zakład Do Utworzenia",
        tryb=BRAK,
        utworzona=None,
    )
    url = reverse("import_pracownikow:jednostki", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    assert resp.status_code == 200
    content = resp.content.decode()
    assert 'data-uczelnia-nieokreslona="1"' in content
    assert "Nie ustalono uczelni" in content


@pytest.mark.django_db
def test_jednostki_bez_ostrzezenia_gdy_uczelnia_znana(admin_client, admin_user):
    """Uczelnia ustalona na imporcie → brak ostrzeżenia, mimo >1 uczelni."""
    baker.make(Uczelnia)
    u = baker.make(Uczelnia)
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        uczelnia=u,
    )
    baker.make(
        ImportPracownikowJednostka,
        parent=imp,
        nazwa_zrodlowa="Zakład Do Utworzenia",
        tryb=BRAK,
        utworzona=None,
    )
    url = reverse("import_pracownikow:jednostki", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    assert resp.status_code == 200
    assert 'data-uczelnia-nieokreslona="1"' not in resp.content.decode()
