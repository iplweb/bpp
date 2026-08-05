import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import StanowiskoDydaktyczne, StopienSluzbowy
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowRow,
    ImportPracownikowStopien,
)
from import_pracownikow.pipeline.integrate import (
    _przygotuj_nowego_autora,
    _rozstrzygnij_stopnie,
    unikalny_skrot_stopnia,
)


@pytest.mark.django_db
def test_unikalny_skrot_stopnia_sufiks():
    baker.make(StopienSluzbowy, nazwa="kapitan", skrot="kpt.")
    assert unikalny_skrot_stopnia("kpt.") != "kpt."


@pytest.mark.django_db
def test_rozstrzygnij_stopnie_tworzy_i_podlacza():
    imp = baker.make(ImportPracownikow)
    dec = baker.make(
        ImportPracownikowStopien,
        parent=imp,
        nazwa_zrodlowa="mł. bryg.",
        tryb=ImportPracownikowStopien.TRYB_BRAK,
        decyzja=ImportPracownikowStopien.DECYZJA_AKCEPTUJ,
        nazwa_do_utworzenia="mł. bryg.",
        skrot_do_utworzenia="mł. bryg.",
        utworzony=None,
    )
    row = baker.make(
        ImportPracownikowRow,
        parent=imp,
        zmiany_potrzebne=False,
        zrodlo_stopnia=dec,
    )
    utworzono = _rozstrzygnij_stopnie(imp, MockProgress(imp))
    assert utworzono == 1
    dec.refresh_from_db()
    row.refresh_from_db()
    assert dec.utworzony is not None
    assert row.stopien == dec.utworzony


@pytest.mark.django_db
def test_nowy_autor_dostaje_stopien_i_email():
    imp = baker.make(ImportPracownikow)
    st = baker.make(StopienSluzbowy, nazwa="brygadier", skrot="bryg.")
    jed = baker.make("bpp.Jednostka")
    row = baker.make(
        ImportPracownikowRow,
        parent=imp,
        zmiany_potrzebne=False,
        confidence="brak",
        utworz_nowego=True,
        autor=None,
        jednostka=jed,
        stopien=st,
        dane_znormalizowane={
            "nazwisko": "Kowalski",
            "imię": "Jan",
            "email": "jan@example.org",
        },
        diff_do_utworzenia={},
    )
    assert _przygotuj_nowego_autora(row, {}) is True
    row.refresh_from_db()
    assert row.autor is not None
    assert row.autor.stopien_sluzbowy == st
    assert row.autor.email == "jan@example.org"


@pytest.mark.django_db
def test_istniejacy_autor_email_no_overwrite():
    imp = baker.make(ImportPracownikow)
    autor = baker.make("bpp.Autor", email="stary@example.org")
    aj = baker.make("bpp.Autor_Jednostka", autor=autor)
    sd = baker.make(StanowiskoDydaktyczne, nazwa="adiunkt", skrot="ad.")
    row = baker.make(
        ImportPracownikowRow,
        parent=imp,
        zmiany_potrzebne=True,
        autor=autor,
        autor_jednostka=aj,
        jednostka=aj.jednostka,
        stanowisko_dydaktyczne=sd,
        dane_znormalizowane={"email": "nowy@example.org"},
        diff_do_utworzenia={},
    )
    row.integrate()
    autor.refresh_from_db()
    aj.refresh_from_db()
    assert autor.email == "stary@example.org"  # NIE nadpisano
    assert aj.stanowisko == sd  # stanowisko overwrite-if-different
