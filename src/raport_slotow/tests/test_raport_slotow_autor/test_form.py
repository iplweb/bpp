import pytest
from django.urls import reverse
from raport_slotow.const import DZIALANIE_SLOT, DZIALANIE_WSZYSTKO
from raport_slotow.forms import AutorRaportSlotowForm
from selenium.webdriver.common.keys import Keys


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


@pytest.mark.selenium
def test_AutorRaportSlotowForm_javascript(admin_browser, live_server):
    url = live_server.url + reverse("raport_slotow:index")
    # with wait_for_page_load(admin_browser):
    admin_browser.visit(url)
    elem = admin_browser.find_by_id("id_slot")
    for x in elem.type(["1", "2", Keys.TAB], slowly=True):
        pass
    res = admin_browser.find_by_id("id_dzialanie_0")
    assert not res.selected

    for x in elem.type([Keys.BACKSPACE, Keys.BACKSPACE, Keys.TAB], slowly=True):
        pass
    res = admin_browser.find_by_id("id_dzialanie_0")
    assert res.selected
