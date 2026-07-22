import pytest
from model_bakery import baker

from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowStopien,
)
from import_pracownikow.pipeline.analyze import (
    _klasyfikuj_stopien_wiersza,
    _ReconcilerJednostek,
    _zrodlo_jednostki_wiersza,
)


@pytest.mark.django_db
def test_klasyfikuj_stopien_twardy_wprost():
    imp = baker.make(ImportPracownikow)
    st = baker.make("bpp.StopienSluzbowy", nazwa="kapitan", skrot="kpt.")
    obj, status, dec = _klasyfikuj_stopien_wiersza(imp, "kpt.", None)
    assert obj == st
    assert status == "twardy"
    assert dec is None


@pytest.mark.django_db
def test_klasyfikuj_stopien_brak_tworzy_decyzje():
    imp = baker.make(ImportPracownikow, tworz_brakujace_stopnie=True)
    from import_pracownikow.pipeline.analyze import _ReconcilerStopni

    rec = _ReconcilerStopni(imp)
    obj, status, dec = _klasyfikuj_stopien_wiersza(imp, "mł. bryg.", rec)
    assert obj is None
    assert status == "brak"
    assert isinstance(dec, ImportPracownikowStopien)
    assert dec.nazwa_zrodlowa == "mł. bryg."


@pytest.mark.django_db
def test_klasyfikuj_stopien_pusty_bez_decyzji():
    imp = baker.make(ImportPracownikow)
    assert _klasyfikuj_stopien_wiersza(imp, "", None) == (None, None, None)


@pytest.mark.django_db
def test_reconciler_jednostek_skrot_hint_nadpisuje_zawsze():
    imp = baker.make(ImportPracownikow)
    rec = _ReconcilerJednostek(imp)
    dec = rec.reconciluj("Zakład X", "brak", None, None, skrot_hint="RW-1/1")
    assert dec.skrot_sugerowany == "RW-1/1"
    # re-analiza z nowym hintem nadpisuje ZAWSZE (nie tylko gdy puste)
    dec2 = rec.reconciluj("Zakład X", "brak", None, None, skrot_hint="RW-9")
    assert dec2.pk == dec.pk
    dec2.refresh_from_db()
    assert dec2.skrot_sugerowany == "RW-9"


@pytest.mark.django_db
def test_zrodlo_jednostki_z_komorki_parsuje_i_daje_skrot_hint():
    # Faza C (#438): „wydział" to jednostka TOP-LEVEL (parent IS NULL).
    baker.make("bpp.Jednostka", nazwa="WIBiOL — pełna", skrot="WIBiOL", parent=None)
    dane = {"komórka_złożona": "RW-6/3 Zakład Nauk Społecznych WIBiOL"}
    nazwa, wydzial, _jed, _st, _sim, skrot_hint = _zrodlo_jednostki_wiersza(dane)
    assert nazwa == "Zakład Nauk Społecznych"
    assert skrot_hint == "RW-6/3"
    assert wydzial == "WIBiOL — pełna"  # oddział→skrót roota→nazwa


@pytest.mark.django_db
def test_zrodlo_jednostki_niepelna_uzywa_klasyfikatora_niepelnego():
    j = baker.make("bpp.Jednostka", nazwa="Wydział Medyczny", widoczna=True)
    dane = {"nazwa_jednostki_niepelna": "Medyczny"}
    nazwa, _wydz, jed, status, _sim, skrot_hint = _zrodlo_jednostki_wiersza(dane)
    assert nazwa == "Medyczny"
    assert jed == j
    assert status == "zgadywanie"
    assert skrot_hint is None
