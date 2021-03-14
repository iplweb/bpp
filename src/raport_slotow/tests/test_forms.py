from raport_slotow.forms import ParametryRaportSlotowEwaluacjaForm


def test_ParametryRaporSlotowEwaluacjaForm_faulty():
    p = ParametryRaportSlotowEwaluacjaForm(
        {"od_roku": "2000", "do_roku": "2000", "_export": "xlsx"}
    )
    p.full_clean()
    assert len(p.errors) == 2


def test_ParametryRaporSlotowEwaluacjaForm_ok():
    p = ParametryRaportSlotowEwaluacjaForm(
        {"od_roku": "2017", "do_roku": "2018", "_export": "xlsx"}
    )
    p.full_clean()
    assert len(p.errors) == 0
