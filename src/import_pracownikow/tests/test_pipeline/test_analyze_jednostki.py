"""Analiza importu pracowników — klasyfikacja jednostki bez rzucania wyjątków.

Niedopasowana jednostka NIE wywala już analizy (dawniej ``XLSMatchError``) —
tworzy decyzję ``ImportPracownikowJednostka`` i odracza wiersz (``jednostka=None``)
do fazy integracji / ekranu weryfikacji.
"""

from unittest.mock import patch

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowJednostka
from import_pracownikow.pewnosc import STATUS_BRAK, STATUS_ZGADYWANIE
from import_pracownikow.pipeline.analyze import analizuj


def _imp(**kwargs):
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY, **kwargs)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    return imp


def _wiersz(nazwa_jednostki, nazwisko="Kowalski", imie="Jan", row=7):
    return {
        "imię": imie,
        "nazwisko": nazwisko,
        "nazwa_jednostki": nazwa_jednostki,
        "__xls_loc_sheet__": 0,
        "__xls_loc_row__": row,
    }


def _analizuj(imp, wiersze):
    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MZ:
        MZ.return_value.count.return_value = len(wiersze)
        MZ.return_value.data.return_value = iter(list(wiersze))
        analizuj(imp, MockProgress(imp))


@pytest.mark.django_db
def test_brak_jednostki_nie_rzuca_tworzy_decyzje_odracza_wiersz():
    imp = _imp()
    _analizuj(imp, [_wiersz("Zakład Transfuzjologii")])

    dec = imp.jednostki_do_decyzji.get()
    assert dec.nazwa_zrodlowa == "Zakład Transfuzjologii"
    assert dec.tryb == ImportPracownikowJednostka.TRYB_BRAK
    assert dec.skrot_sugerowany == "ZT"

    row = imp.importpracownikowrow_set.get()
    assert row.jednostka_id is None
    assert row.jednostka_status == STATUS_BRAK
    assert row.zrodlo_jednostki_id == dec.pk
    assert "autor_jednostka" not in (row.diff_do_utworzenia or {})
    assert row.zmiany_potrzebne is False


@pytest.mark.django_db
def test_zgadywanie_jednostki_zapisuje_auto_dopasowanie(uczelnia):
    j = baker.make(
        Jednostka, nazwa="Zakład Transfuzjologii", skrot="ZT", uczelnia=uczelnia
    )
    imp = _imp()
    # wariant bez diakrytyków → trigram wysoki, ale nie dokładny
    _analizuj(imp, [_wiersz("Zaklad Transfuzjologii")])

    dec = imp.jednostki_do_decyzji.get()
    assert dec.tryb == ImportPracownikowJednostka.TRYB_ZGADYWANIE
    assert dec.auto_jednostka_id == j.pk
    assert dec.auto_similarity is not None and dec.auto_similarity >= 0.7

    row = imp.importpracownikowrow_set.get()
    assert row.jednostka_id is None  # odroczone do integracji
    assert row.jednostka_status == STATUS_ZGADYWANIE
    assert row.zrodlo_jednostki_id == dec.pk


@pytest.mark.django_db
def test_pusta_nazwa_jednostki_pomija_bez_crasha():
    imp = _imp()
    _analizuj(imp, [_wiersz("")])

    assert not imp.jednostki_do_decyzji.exists()
    row = imp.importpracownikowrow_set.get()
    assert row.jednostka_id is None
    assert row.jednostka_status == STATUS_BRAK
    assert row.zrodlo_jednostki_id is None
    assert row.zmiany_potrzebne is False


@pytest.mark.django_db
def test_toggle_off_nie_tworzy_decyzji_brak():
    imp = _imp(tworz_brakujace_jednostki=False)
    _analizuj(imp, [_wiersz("Zakład Transfuzjologii")])

    assert not imp.jednostki_do_decyzji.exists()
    row = imp.importpracownikowrow_set.get()
    assert row.jednostka_id is None
    assert row.zrodlo_jednostki_id is None


@pytest.mark.django_db
def test_decyzja_dedup_po_nazwie_dwa_wiersze_jedna_decyzja():
    imp = _imp()
    _analizuj(
        imp,
        [
            _wiersz("Zakład Transfuzjologii", nazwisko="Kowalski", row=1),
            _wiersz("Zakład Transfuzjologii", nazwisko="Nowak", row=2),
        ],
    )
    assert imp.jednostki_do_decyzji.count() == 1
    dec = imp.jednostki_do_decyzji.get()
    assert imp.importpracownikowrow_set.filter(zrodlo_jednostki=dec).count() == 2


@pytest.mark.django_db
def test_reanaliza_zachowuje_wybor_usera_i_usuwa_stale():
    imp = _imp()
    _analizuj(imp, [_wiersz("Zakład A", row=1), _wiersz("Zakład B", row=2)])
    dec_a = imp.jednostki_do_decyzji.get(nazwa_zrodlowa="Zakład A")
    dec_a.decyzja = ImportPracownikowJednostka.DECYZJA_POMIN
    dec_a.save()

    # symuluj on_restart (kasuje wiersze) + re-analizę zmienionego pliku
    imp.importpracownikowrow_set.all().delete()
    _analizuj(imp, [_wiersz("Zakład A", row=1), _wiersz("Zakład C", row=2)])

    dec_a.refresh_from_db()
    assert dec_a.decyzja == ImportPracownikowJednostka.DECYZJA_POMIN  # wybór został
    assert not imp.jednostki_do_decyzji.filter(
        nazwa_zrodlowa="Zakład B"
    ).exists()  # stale
    assert imp.jednostki_do_decyzji.filter(nazwa_zrodlowa="Zakład C").exists()  # nowa
