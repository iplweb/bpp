import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Jednostka
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowRow,
    ImportPracownikowRowKandydat,
)
from import_pracownikow.pewnosc import STATUS_TWARDY, STATUS_WIELU


@pytest.mark.django_db
def test_podglad_pokazuje_badge_i_dropdown_kandydatow(admin_client, admin_user):
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    a1 = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=None,
        confidence=STATUS_WIELU,
        zmiany_potrzebne=False,
        dane_znormalizowane={"imię": "Jan", "nazwisko": "Kowalski"},
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 7},
    )
    ImportPracownikowRowKandydat.objects.create(
        row=row, autor=a1, pewnosc=1.0, powod="iexact"
    )
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    tresc = resp.content.decode("utf-8")
    assert resp.status_code == 200
    # KONKRETNY badge statusu „wielu" (Foundation label primary + ikona +
    # etykieta) — nie samo „label"/„fi-", które przeciekają z base.html.
    assert "label primary" in tresc
    assert "fi-page-multiple" in tresc
    assert "wielu kandydatów" in tresc
    # dropdown kandydatów dla wielu (HTMX POST na wybierz-kandydata)
    assert (
        reverse(
            "import_pracownikow:wybierz-kandydata",
            kwargs={"pk": imp.pk, "row_pk": row.pk},
        )
        in tresc
    )


@pytest.mark.django_db
def test_podglad_sortuje_nie_twardy_na_gore(admin_client, admin_user):
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
    )
    jednostka = baker.make(Jednostka, nazwa="Kat.", skrot="K.")
    autor = baker.make(Autor, nazwisko="Zz", imiona="Aa")
    twardy = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=autor,
        confidence=STATUS_TWARDY,
        zmiany_potrzebne=True,
        dane_znormalizowane={},
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 1},
    )
    wielu = ImportPracownikowRow.objects.create(
        parent=imp,
        jednostka=jednostka,
        autor=None,
        confidence=STATUS_WIELU,
        zmiany_potrzebne=False,
        dane_znormalizowane={},
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 9},
    )
    from import_pracownikow.views import ImportPracownikowResultsView

    view = ImportPracownikowResultsView()
    view.kwargs = {"pk": imp.pk}
    view.request = type("R", (), {"user": admin_user})()
    lista = list(view.get_queryset())
    # non-twardy (wielu) mimo wyższego nr wiersza jest PRZED twardym
    assert lista[0].pk == wielu.pk
    assert lista[1].pk == twardy.pk
