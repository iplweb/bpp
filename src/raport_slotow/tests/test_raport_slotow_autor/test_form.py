from raport_slotow.const import DZIALANIE_SLOT, DZIALANIE_WSZYSTKO
from raport_slotow.forms.autor import AutorRaportSlotowForm


def test_AutorRaportSlotowForm_clean_lata(autor_jan_kowalski):
    af = AutorRaportSlotowForm(
        dict(
            obiekt=autor_jan_kowalski,
            od_roku=2020,
            do_roku=2018,
            minimalny_pk=0,
            dzialanie="wszystko",
            _export="html",
        )
    )
    af.full_clean()
    assert af.has_error("od_roku", code="od_do_zle")


def test_AutorRaportSlotowForm_clean_dzialanie_wszystko(autor_jan_kowalski):
    af = AutorRaportSlotowForm(
        dict(
            obiekt=autor_jan_kowalski,
            od_roku=2018,
            do_roku=2020,
            minimalny_pk=0,
            dzialanie=DZIALANIE_WSZYSTKO,
            slot=15,
            _export="html",
        )
    )
    af.full_clean()
    assert af.has_error("slot", code="nie_podawaj_gdy_wszystko")


def test_AutorRaportSlotowForm_clean_dzialanie_slot_brak(autor_jan_kowalski):
    af = AutorRaportSlotowForm(
        dict(
            obiekt=autor_jan_kowalski,
            od_roku=2018,
            do_roku=2020,
            minimalny_pk=0,
            dzialanie=DZIALANIE_SLOT,
            _export="html",
        )
    )
    af.full_clean()
    assert af.has_error("slot", code="podawaj_gdy_slot")


def test_AutorRaportSlotowForm_clean_dzialanie_slot_zero(autor_jan_kowalski):
    af = AutorRaportSlotowForm(
        dict(
            obiekt=autor_jan_kowalski,
            od_roku=2018,
            do_roku=2020,
            minimalny_pk=0,
            slot=0,
            dzialanie=DZIALANIE_SLOT,
            _export="html",
        )
    )
    af.full_clean()
    assert af.has_error("slot", code="podawaj_gdy_slot")
