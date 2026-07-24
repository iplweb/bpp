import pytest
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from raport_slotow.models.uczelnia import (
    RaportSlotowUczelnia,
    RaportSlotowUczelniaWiersz,
)


def test_ListaRaportSlotowUczelnia(admin_client, admin_user):
    # liveops list-view NIE kasuje starych operacji (housekeeping to nie jego
    # zadanie — porzucona quirk long_running.LongRunningOperationsView).
    for no in range(20):
        baker.make(
            RaportSlotowUczelnia, owner=admin_user, od_roku=2000 + no, do_roku=2000 + no
        )

    assert RaportSlotowUczelnia.objects.count() == 20

    res = admin_client.get(reverse("raport_slotow:lista-raport-slotow-uczelnia"))

    assert res.status_code == 200
    # Nic nie zostało skasowane.
    assert RaportSlotowUczelnia.objects.count() == 20


def test_StronaLiveRaportuSlotowUczelnia(admin_client, admin_user):
    # Dawny „-details"/„-router" zastąpiła centralna strona live liveops
    # (get_absolute_url → liveops:live).
    rsu = baker.make(RaportSlotowUczelnia, owner=admin_user)
    res = admin_client.get(rsu.get_absolute_url())
    assert res.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("dziel_na_jednostki_i_wydzialy", [True, False])
def test_SzczegolyRaportuSlotowUczelniaListaRekordow(
    admin_client, admin_user, dziel_na_jednostki_i_wydzialy
):
    rsu = baker.make(
        RaportSlotowUczelnia,
        owner=admin_user,
        dziel_na_jednostki_i_wydzialy=dziel_na_jednostki_i_wydzialy,
    )
    baker.make(RaportSlotowUczelniaWiersz, parent=rsu)

    admin_client.get(
        reverse(
            "raport_slotow:raportslotowuczelnia-results",
            args=(rsu.pk,),
        )
    )

    res = admin_client.get(
        reverse(
            "raport_slotow:raportslotowuczelnia-results",
            args=(rsu.pk,),
        )
        + "?_export=xlsx"
    )
    assert res["content-type"] == "application/vnd.ms-excel"


def test_RegenerujRaportuSlotowUczelnia(admin_client, admin_user):
    # Regen jest POST-only (liveops RestartView). Raport skończony → reset +
    # re-enqueue; pod runnerem eager run() biegnie synchronicznie i finished_on
    # się zmienia.
    rsu = baker.make(
        RaportSlotowUczelnia,
        owner=admin_user,
        finished_successfully=True,
        finished_on=timezone.now(),
    )
    first_finished_on = rsu.finished_on
    baker.make(RaportSlotowUczelniaWiersz, parent=rsu)

    admin_client.post(
        reverse("raport_slotow:raportslotowuczelnia-regen", args=(rsu.pk,))
    )

    rsu.refresh_from_db()
    assert rsu.finished_on != first_finished_on


def test_RegenerujRaportuSlotowUczelnia_get_zabroniony(admin_client, admin_user):
    # GET nie mutuje (405) — regen jest POST-only.
    rsu = baker.make(
        RaportSlotowUczelnia,
        owner=admin_user,
        finished_successfully=True,
        finished_on=timezone.now(),
    )
    res = admin_client.get(
        reverse("raport_slotow:raportslotowuczelnia-regen", args=(rsu.pk,))
    )
    assert res.status_code == 405


def test_RegenerujRaportuSlotowUczelnia_nieskonczony_nie_resetuje(
    admin_client, admin_user
):
    # Guard §8.4: regen na nie-skończonym raporcie (biegnie / nie wystartował)
    # NIE resetuje ani nie kasuje wierszy — chroni przed wyścigiem z workerem.
    rsu = baker.make(RaportSlotowUczelnia, owner=admin_user)  # NOT_STARTED
    baker.make(RaportSlotowUczelniaWiersz, parent=rsu)

    admin_client.post(
        reverse("raport_slotow:raportslotowuczelnia-regen", args=(rsu.pk,))
    )

    rsu.refresh_from_db()
    # Nie wystartował (guard nie odpalił enqueue) i wiersze nietknięte.
    assert rsu.started_on is None
    assert rsu.raportslotowuczelniawiersz_set.count() == 1


def test_RegenerujRaportuSlotowUczelnia_anon_302_bez_efektu(client, admin_user):
    # Bramka autoryzacji: anonimowy POST → 302 na login (NIE 403), bez efektu
    # ubocznego (raport nietknięty).
    rsu = baker.make(
        RaportSlotowUczelnia,
        owner=admin_user,
        finished_successfully=True,
        finished_on=timezone.now(),
    )
    first_finished_on = rsu.finished_on

    res = client.post(
        reverse("raport_slotow:raportslotowuczelnia-regen", args=(rsu.pk,))
    )

    assert res.status_code == 302
    assert "login" in res["Location"].lower()
    rsu.refresh_from_db()
    assert rsu.finished_on == first_finished_on


@pytest.mark.django_db
def test_UtworzRaportSlotowUczelnia_anon_302(client):
    # Widok tworzenia dzieli ten sam _LiveopsNoPermissionCompatMixin co Regen
    # (kolizja MRO braces vs liveops handle_no_permission). Anon → 302 na
    # login, NIGDY 500 (TypeError z bez-argumentowego handle_no_permission).
    res = client.get(reverse("raport_slotow:utworz-raport-slotow-uczelnia"))
    assert res.status_code == 302
    assert "login" in res["Location"].lower()
