import pytest
from django.urls import reverse
from django_webtest import DjangoWebtestResponse
from model_bakery import baker

from raport_slotow.models.uczelnia import RaportSlotowUczelnia

from django.utils import timezone


@pytest.fixture
def raport_slotow_uczelnia(uczelnia, admin_user) -> RaportSlotowUczelnia:
    return baker.make(
        RaportSlotowUczelnia, owner=admin_user, finished_on=timezone.now()
    )


@pytest.fixture
def raport_slotow_uczelnia_wiersz(
    raport_slotow_uczelnia,
    autor_jan_nowak,
    jednostka,
    dyscyplina1,
):
    return raport_slotow_uczelnia.raportslotowuczelniawiersz_set.create(
        autor=autor_jan_nowak,
        jednostka=jednostka,
        dyscyplina=dyscyplina1,
        pkd_aut_sum=10.0,
        slot=1.0,
        avg=5,
    )


@pytest.fixture
def raport_slotow_uczelnia_page(
    raport_slotow_uczelnia: RaportSlotowUczelnia,
    admin_app,
    admin_user,
    dyscyplina1,
    praca_z_dyscyplina,
) -> DjangoWebtestResponse:

    res = admin_app.get(
        reverse(
            "raport_slotow:raportslotowuczelnia-results",
            kwargs={"pk": raport_slotow_uczelnia.id},
        )
    )
    return res


def test_raport_uczelnia_filtry_autor__nazwisko(
    raport_slotow_uczelnia_page,
):
    # Find the filter form (not the logout form)
    filter_form = None
    for form in raport_slotow_uczelnia_page.forms.values():
        if "autor__nazwisko" in form.fields:
            filter_form = form
            break

    assert filter_form is not None, "Filter form not found"
    filter_form["autor__nazwisko"] = "test"
    assert filter_form.submit().status_code == 200


def test_raport_uczelnia_filtry_dyscyplina(
    raport_slotow_uczelnia_page,
    dyscyplina1,
):
    # Find the filter form (not the logout form)
    filter_form = None
    for form in raport_slotow_uczelnia_page.forms.values():
        if "dyscyplina" in form.fields:
            filter_form = form
            break

    assert filter_form is not None, "Filter form not found"
    filter_form["dyscyplina"] = dyscyplina1.pk
    assert filter_form.submit().status_code == 200


def test_raport_uczelnia_filtry_suma__min(
    raport_slotow_uczelnia_page,
):
    # Find the filter form (not the logout form)
    filter_form = None
    for form in raport_slotow_uczelnia_page.forms.values():
        if "suma__min" in form.fields:
            filter_form = form
            break

    assert filter_form is not None, "Filter form not found"
    filter_form["suma__min"] = 5
    assert filter_form.submit().status_code == 200


def test_raport_uczelnia_filtry_slot__min(
    raport_slotow_uczelnia_page,
):
    # Find the filter form (not the logout form)
    filter_form = None
    for form in raport_slotow_uczelnia_page.forms.values():
        if "slot__min" in form.fields:
            filter_form = form
            break

    assert filter_form is not None, "Filter form not found"
    filter_form["slot__min"] = 5
    assert filter_form.submit().status_code == 200


def test_raport_uczelnia_filtry_avg__min(
    raport_slotow_uczelnia_page,
):
    # Find the filter form (not the logout form)
    filter_form = None
    for form in raport_slotow_uczelnia_page.forms.values():
        if "avg__min" in form.fields:
            filter_form = form
            break

    assert filter_form is not None, "Filter form not found"
    filter_form["avg__min"] = 5
    assert filter_form.submit().status_code == 200


def test_raport_uczelnia_xlsx(raport_slotow_uczelnia_wiersz, admin_app):
    res = admin_app.get(
        reverse(
            "raport_slotow:raportslotowuczelnia-results",
            kwargs={"pk": raport_slotow_uczelnia_wiersz.parent.id},
        )
    )

    assert res.click("Pobierz w formacie XLSX").status_code == 200


def test_raport_uczelnia_xlsx_ponizej_limitu_przechodzi(
    raport_slotow_uczelnia_wiersz, admin_app, monkeypatch
):
    # Poniżej limitu (2 wiersze < 3) → normalny eksport XLSX (HTTP 200).
    from raport_slotow.views.uczelnia import (
        SzczegolyRaportSlotowUczelniaListaRekordow,
    )

    parent = raport_slotow_uczelnia_wiersz.parent
    parent.raportslotowuczelniawiersz_set.create(
        autor=raport_slotow_uczelnia_wiersz.autor,
        jednostka=raport_slotow_uczelnia_wiersz.jednostka,
        dyscyplina=raport_slotow_uczelnia_wiersz.dyscyplina,
        pkd_aut_sum=1.0,
        slot=1.0,
        avg=1,
    )
    monkeypatch.setattr(
        SzczegolyRaportSlotowUczelniaListaRekordow, "export_max_rows", 3
    )

    res = admin_app.get(
        reverse(
            "raport_slotow:raportslotowuczelnia-results",
            kwargs={"pk": parent.id},
        ),
        params={"_export": "xlsx"},
    )
    assert res.status_code == 200
    assert res.content_type != "text/html"


def test_raport_uczelnia_xlsx_powyzej_limitu_zwraca_400(
    raport_slotow_uczelnia_wiersz, admin_app, monkeypatch
):
    # Przekroczenie limitu → HTTP 400 z czytelnym komunikatem (bez cichego
    # ucięcia pliku). Limit obniżamy monkeypatchem, żeby nie tworzyć dziesiątek
    # tysięcy wierszy w teście.
    from raport_slotow.views.uczelnia import (
        SzczegolyRaportSlotowUczelniaListaRekordow,
    )

    parent = raport_slotow_uczelnia_wiersz.parent
    # Drugi wiersz: 2 > limit=1.
    parent.raportslotowuczelniawiersz_set.create(
        autor=raport_slotow_uczelnia_wiersz.autor,
        jednostka=raport_slotow_uczelnia_wiersz.jednostka,
        dyscyplina=raport_slotow_uczelnia_wiersz.dyscyplina,
        pkd_aut_sum=1.0,
        slot=1.0,
        avg=1,
    )
    monkeypatch.setattr(
        SzczegolyRaportSlotowUczelniaListaRekordow, "export_max_rows", 1
    )

    res = admin_app.get(
        reverse(
            "raport_slotow:raportslotowuczelnia-results",
            kwargs={"pk": parent.id},
        ),
        params={"_export": "xlsx"},
        expect_errors=True,
    )
    assert res.status_code == 400
    assert "maksymalnie 1" in res.text
    assert "2" in res.text
