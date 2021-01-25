import pytest
from django.core.exceptions import ValidationError

from raport_slotow.models.uczelnia import (
    RaportSlotowUczelnia,
    RaportSlotowUczelniaWiersz,
)


def test_RaportSlotowUczelnia_get_absolute_url(raport_slotow_uczelnia):
    assert raport_slotow_uczelnia.get_absolute_url()


def test_RaportSlotowUczelnia_clean():
    r = RaportSlotowUczelnia(od_roku=2020, do_roku=2010)
    with pytest.raises(ValidationError):
        r.clean()


def test_RaportSlotowUczelnia_create_report(rekord_slotu, rok, raport_slotow_uczelnia):
    raport_slotow_uczelnia.od_roku = rok
    raport_slotow_uczelnia.do_roku = rok
    raport_slotow_uczelnia.save()

    assert RaportSlotowUczelniaWiersz.objects.count() == 0
    raport_slotow_uczelnia.create_report()

    assert RaportSlotowUczelniaWiersz.objects.count() == 1
