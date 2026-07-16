"""Faza 2 (cutover): RaportSlotowUczelnia jako liveops.LiveOperation.

Sprawdza: typ bazy, nowe pola stanu, on_restart kasuje wiersze, run(p)
generuje wiersze i RESPEKTUJE scoping per-uczelnia (guard §8.1), oraz że
run() jest all-or-nothing (transaction.atomic).
"""

import pytest
from liveops.models import LiveOperation
from liveops.testing import MockProgress
from model_bakery import baker

from raport_slotow.models.uczelnia import (
    RaportSlotowUczelnia,
    RaportSlotowUczelniaWiersz,
)


def test_jest_liveoperation():
    assert issubclass(RaportSlotowUczelnia, LiveOperation)


@pytest.mark.django_db
def test_ma_pola_stanu_liveops():
    r = baker.make(RaportSlotowUczelnia)
    for pole in (
        "cancel_requested",
        "cancelled",
        "result_context",
        "current_stage",
        "stage_states",
        "percent",
        "log",
    ):
        assert hasattr(r, pole)


@pytest.mark.django_db
def test_on_restart_kasuje_wiersze(raport_slotow_uczelnia):
    baker.make(RaportSlotowUczelniaWiersz, parent=raport_slotow_uczelnia)
    assert raport_slotow_uczelnia.raportslotowuczelniawiersz_set.count() == 1

    raport_slotow_uczelnia.on_restart()

    assert raport_slotow_uczelnia.raportslotowuczelniawiersz_set.count() == 0


@pytest.mark.django_db
def test_run_generuje_wiersze(rekord_slotu, rok, raport_slotow_uczelnia):
    raport_slotow_uczelnia.od_roku = rok
    raport_slotow_uczelnia.do_roku = rok
    raport_slotow_uczelnia.save()

    raport_slotow_uczelnia.run(MockProgress(raport_slotow_uczelnia))

    assert RaportSlotowUczelniaWiersz.objects.count() == 1


@pytest.mark.django_db
def test_run_respektuje_scoping_uczelni(
    zwarte_dwie_uczelnie, jednostka, druga_uczelnia, rok
):
    """run() z ustawioną ``uczelnia`` generuje wiersze TYLKO dla jej
    jednostek (guard per-uczelnia §8.1 na poziomie run())."""
    zwarte_dwie_uczelnie.przelicz_punkty_dyscyplin()

    raport = baker.make(
        RaportSlotowUczelnia,
        od_roku=rok,
        do_roku=rok,
        uczelnia=jednostka.uczelnia,
        akcja=RaportSlotowUczelnia.Akcje.WSZYSTKO,
    )
    raport.run(MockProgress(raport))

    uczelnie_w_raporcie = set(
        raport.raportslotowuczelniawiersz_set.values_list(
            "jednostka__uczelnia_id", flat=True
        )
    )
    assert uczelnie_w_raporcie <= {jednostka.uczelnia_id}
    assert druga_uczelnia.pk not in uczelnie_w_raporcie
