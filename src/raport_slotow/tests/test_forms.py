import pytest
from django.core.exceptions import ValidationError

from raport_slotow.forms import ParametryRaportSlotowEwaluacjaForm


def test_ParametryRaporSlotowEwaluacjaForm_faulty():
    p = ParametryRaportSlotowEwaluacjaForm(
        {"od_roku": 2020, "do_roku": 2010, "_export": "xlsx"}
    )
    p.full_clean()
    assert len(p.errors) == 1


def test_ParametryRaporSlotowEwaluacjaForm_ok():
    p = ParametryRaportSlotowEwaluacjaForm(
        {"od_roku": 2000, "do_roku": 2010, "_export": "xlsx"}
    )
    p.full_clean()
    assert len(p.errors) == 0
