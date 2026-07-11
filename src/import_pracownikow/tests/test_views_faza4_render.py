import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor_Jednostka
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowOdpiecie,
    ImportPracownikowRow,
)
from import_pracownikow.pewnosc import STATUS_BRAK


def _results_url(imp):
    return reverse(
        "import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk}
    )


@pytest.mark.django_db
def test_render_checkbox_utworz_nowego_dla_brak(admin_client, admin_user):
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
    )
    ImportPracownikowRow.objects.create(
        parent=imp,
        confidence=STATUS_BRAK,
        zmiany_potrzebne=False,
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 0},
        dane_znormalizowane={"nazwisko": "Nowak", "imię": "Jan"},
    )
    resp = admin_client.get(_results_url(imp))
    tresc = resp.content.decode("utf-8")
    assert 'name="utworz_nowego"' in tresc
    assert "utwórz nowego" in tresc


@pytest.mark.django_db
def test_render_sekcja_odpiec_z_checkboxem(admin_client, admin_user):
    # Sekcja odpięć przeniesiona z results do OdpieciaView (T2.3) — renderuje
    # się teraz na podstronie `odpiecia`, nie na tabeli wierszy.
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
    )
    aj = baker.make(Autor_Jednostka, autor__nazwisko="Odpinalski")
    ImportPracownikowOdpiecie.objects.create(parent=imp, autor_jednostka=aj)
    url = reverse("import_pracownikow:odpiecia", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    tresc = resp.content.decode("utf-8")
    assert "Odpinalski" in tresc
    assert 'name="zaznaczone"' in tresc
