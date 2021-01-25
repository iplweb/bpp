import pytest
from django.urls import reverse
from model_mommy import mommy

from raport_slotow.models.uczelnia import (
    RaportSlotowUczelnia,
    RaportSlotowUczelniaWiersz,
)


def test_ListaRaportSlotowUczelnia(admin_client, admin_user):

    for no in range(20):
        mommy.make(
            RaportSlotowUczelnia, owner=admin_user, od_roku=2000 + no, do_roku=2000 + no
        )

    assert RaportSlotowUczelnia.objects.count() == 20

    admin_client.get(reverse("raport_slotow:lista-raport-slotow-uczelnia"))

    assert RaportSlotowUczelnia.objects.count() == 10


def test_SzczegolyRaportuSlotowUczelnia(admin_client, admin_user):
    rsu = mommy.make(RaportSlotowUczelnia, owner=admin_user)
    admin_client.get(
        reverse("raport_slotow:szczegoly-raport-slotow-uczelnia", args=(rsu.pk,))
    )


@pytest.mark.parametrize("dziel_na_jednostki_i_wydzialy", [True, False])
def test_SzczegolyRaportuSlotowUczelniaListaRekordow(
    admin_client, admin_user, dziel_na_jednostki_i_wydzialy
):
    rsu = mommy.make(
        RaportSlotowUczelnia,
        owner=admin_user,
        dziel_na_jednostki_i_wydzialy=dziel_na_jednostki_i_wydzialy,
    )
    mommy.make(RaportSlotowUczelniaWiersz, parent=rsu)

    admin_client.get(
        reverse(
            "raport_slotow:szczegoly-raport-slotow-uczelnia-lista-rekordow",
            args=(rsu.pk,),
        )
    )

    res = admin_client.get(
        reverse(
            "raport_slotow:szczegoly-raport-slotow-uczelnia-lista-rekordow",
            args=(rsu.pk,),
        )
        + "?_export=xlsx"
    )
    assert res["content-type"] == "application/vnd.ms-excel"
