import pytest
from django.urls import reverse
from model_bakery import baker

from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pewnosc import STATUS_BRAK, STATUS_TWARDY


def _wiersz(owner, confidence=STATUS_BRAK, stan=ImportPracownikow.STAN_PRZEANALIZOWANY):
    imp = baker.make(ImportPracownikow, owner=owner, stan=stan)
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        confidence=confidence,
        zmiany_potrzebne=False,
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 0},
        dane_znormalizowane={"nazwisko": "Nowak", "imię": "Jan"},
    )
    return imp, row


@pytest.mark.django_db
def test_toggle_utworz_nowego_ustawia_flage(admin_client, admin_user):
    imp, row = _wiersz(admin_user)
    url = reverse(
        "import_pracownikow:utworz-nowego",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"utworz_nowego": "on"})
    assert resp.status_code == 200
    row.refresh_from_db()
    assert row.utworz_nowego is True

    resp = admin_client.post(url, {})
    row.refresh_from_db()
    assert row.utworz_nowego is False


@pytest.mark.django_db
def test_toggle_odrzuca_wiersz_nie_brak(admin_client, admin_user):
    imp, row = _wiersz(admin_user, confidence=STATUS_TWARDY)
    url = reverse(
        "import_pracownikow:utworz-nowego",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"utworz_nowego": "on"})
    assert resp.status_code == 400
    row.refresh_from_db()
    assert row.utworz_nowego is False


@pytest.mark.django_db
def test_toggle_blokada_poza_podgladem(admin_client, admin_user):
    imp, row = _wiersz(admin_user, stan=ImportPracownikow.STAN_ZINTEGROWANY)
    url = reverse(
        "import_pracownikow:utworz-nowego",
        kwargs={"pk": imp.pk, "row_pk": row.pk},
    )
    resp = admin_client.post(url, {"utworz_nowego": "on"})
    assert resp.status_code == 400
