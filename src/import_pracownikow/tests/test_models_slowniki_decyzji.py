import pytest
from model_bakery import baker

from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowRow,
    ImportPracownikowStanowisko,
    ImportPracownikowStopien,
)


@pytest.mark.django_db
def test_decyzja_stopnia_ma_relacje_i_stale():
    imp = baker.make(ImportPracownikow)
    dec = baker.make(ImportPracownikowStopien, parent=imp, nazwa_zrodlowa="kpt.")
    assert dec in imp.stopnie_do_decyzji.all()
    assert (
        dec.tryb
        in {
            ImportPracownikowStopien.TRYB_ZGADYWANIE,
            ImportPracownikowStopien.TRYB_BRAK,
        }
        or dec.tryb is not None
    )
    assert ImportPracownikowStopien.DECYZJA_AKCEPTUJ == "akceptuj"
    assert ImportPracownikowStopien.DECYZJA_POMIN == "pomin"


@pytest.mark.django_db
def test_decyzja_stanowiska_ma_relacje():
    imp = baker.make(ImportPracownikow)
    dec = baker.make(ImportPracownikowStanowisko, parent=imp, nazwa_zrodlowa="adiunkt")
    assert dec in imp.stanowiska_do_decyzji.all()


@pytest.mark.django_db
def test_row_ma_fk_stopnia_i_stanowiska_dydaktycznego():
    imp = baker.make(ImportPracownikow)
    st = baker.make("bpp.StopienSluzbowy", nazwa="kapitan", skrot="kpt.")
    sd = baker.make("bpp.StanowiskoDydaktyczne", nazwa="adiunkt", skrot="ad.")
    dec_st = baker.make(ImportPracownikowStopien, parent=imp, nazwa_zrodlowa="kpt.")
    dec_sd = baker.make(
        ImportPracownikowStanowisko, parent=imp, nazwa_zrodlowa="adiunkt"
    )
    row = baker.make(
        ImportPracownikowRow,
        parent=imp,
        zmiany_potrzebne=False,
        stopien=st,
        stopien_status="twardy",
        zrodlo_stopnia=dec_st,
        stanowisko_dydaktyczne=sd,
        stanowisko_dydaktyczne_status="twardy",
        zrodlo_stanowiska_dydaktycznego=dec_sd,
    )
    row.refresh_from_db()
    assert row.stopien == st
    assert row.stanowisko_dydaktyczne == sd
    assert row in dec_st.wiersze_stopien.all()
    assert row in dec_sd.wiersze_stanowisko.all()


@pytest.mark.django_db
def test_toggle_slownikow_domyslnie_wlaczone():
    imp = baker.make(ImportPracownikow)
    assert imp.tworz_brakujace_stopnie is True
    assert imp.tworz_brakujace_stanowiska is True
