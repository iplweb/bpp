from raport_slotow.forms import ParametryRaportSlotowEwaluacjaForm


def test_ParametryRaporSlotowEwaluacjaForm_faulty():
    p = ParametryRaportSlotowEwaluacjaForm({"rok": "2000", "_export": "xlsx"})
    p.full_clean()
    assert len(p.errors) == 1


def test_ParametryRaporSlotowEwaluacjaForm_ok():
    p = ParametryRaportSlotowEwaluacjaForm({"rok": "2017", "_export": "xlsx"})
    p.full_clean()
    assert len(p.errors) == 0
