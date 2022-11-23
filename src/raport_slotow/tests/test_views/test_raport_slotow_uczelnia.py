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
    raport_slotow_uczelnia_page.forms[0]["autor__nazwisko"] = "test"
    assert raport_slotow_uczelnia_page.forms[0].submit().status_code == 200


def test_raport_uczelnia_filtry_dyscyplina(
    raport_slotow_uczelnia_page,
    dyscyplina1,
):

    raport_slotow_uczelnia_page.forms[0]["dyscyplina"] = dyscyplina1.pk
    assert raport_slotow_uczelnia_page.forms[0].submit().status_code == 200


def test_raport_uczelnia_filtry_suma__min(
    raport_slotow_uczelnia_page,
):

    raport_slotow_uczelnia_page.forms[0]["suma__min"] = 5
    assert raport_slotow_uczelnia_page.forms[0].submit().status_code == 200


def test_raport_uczelnia_filtry_slot__min(
    raport_slotow_uczelnia_page,
):

    raport_slotow_uczelnia_page.forms[0]["slot__min"] = 5
    assert raport_slotow_uczelnia_page.forms[0].submit().status_code == 200


def test_raport_uczelnia_filtry_avg__min(
    raport_slotow_uczelnia_page,
):

    raport_slotow_uczelnia_page.forms[0]["avg__min"] = 5
    assert raport_slotow_uczelnia_page.forms[0].submit().status_code == 200


def test_raport_uczelnia_xlsx(raport_slotow_uczelnia_wiersz, admin_app):
    res = admin_app.get(
        reverse(
            "raport_slotow:raportslotowuczelnia-results",
            kwargs={"pk": raport_slotow_uczelnia_wiersz.parent.id},
        )
    )

    assert res.click("Pobierz w formacie XLSX").status_code == 200
