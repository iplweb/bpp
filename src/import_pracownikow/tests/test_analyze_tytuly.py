"""Analiza importu pracowników — klasyfikacja tytułu bez rzucania wyjątków.

Mirror ``test_pipeline/test_analyze_jednostki.py`` dla tytułów (Task B2 / T3.3).
Niedopasowany tytuł NIE wywala analizy — tworzy decyzję ``ImportPracownikowTytul``
i odracza wiersz (``tytul=None``) do fazy integracji / ekranu weryfikacji.
Tytuł dopasowany dokładnie (``twardy``) trafia na wiersz wprost, bez decyzji.
"""

from unittest.mock import patch

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Tytul
from import_common.core.tytul import (
    STATUS_TYTUL_BRAK,
    STATUS_TYTUL_TWARDY,
)
from import_pracownikow.models import ImportPracownikow, ImportPracownikowTytul
from import_pracownikow.pipeline.analyze import analizuj

# String pewny, że NIE istnieje w słowniku ``Tytul`` (ani jako dokładne, ani
# jako bliskie trigramowo dopasowanie) — klasyfikuje się jako ``brak``.
NIEDOPASOWANY = "Superhiperdoktorat XYZ"


def _imp(**kwargs):
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY, **kwargs)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    return imp


def _wiersz(tytul, nazwisko="Kowalski", imie="Jan", row=7):
    return {
        "imię": imie,
        "nazwisko": nazwisko,
        "tytuł_stopień": tytul,
        "__xls_loc_sheet__": 0,
        "__xls_loc_row__": row,
    }


def _analizuj(imp, wiersze):
    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MZ:
        MZ.return_value.count.return_value = len(wiersze)
        MZ.return_value.data.return_value = iter(list(wiersze))
        analizuj(imp, MockProgress(imp))


@pytest.mark.django_db
def test_brak_tytulu_tworzy_decyzje_odracza_wiersz():
    imp = _imp()
    _analizuj(imp, [_wiersz(NIEDOPASOWANY)])

    dec = imp.tytuly_do_decyzji.get()
    assert dec.nazwa_zrodlowa == NIEDOPASOWANY
    assert dec.tryb == ImportPracownikowTytul.TRYB_BRAK
    assert dec.auto_tytul_id is None
    # przy CREATE zasilamy edytowalne pola „do utworzenia”
    assert dec.nazwa_do_utworzenia == NIEDOPASOWANY
    assert dec.skrot_do_utworzenia == NIEDOPASOWANY

    row = imp.importpracownikowrow_set.get()
    assert row.tytul_id is None  # odroczony do integracji
    assert row.tytul_status == STATUS_TYTUL_BRAK
    assert row.zrodlo_tytulu_id == dec.pk


@pytest.mark.django_db
def test_tytul_twardy_bez_decyzji_na_wierszu_wprost():
    # dokładne dopasowanie po ``normalize_tytul`` (kropki/wielkość liter):
    # „dr test.” == „Dr. Test”.
    t = baker.make(Tytul, nazwa="Doktor Testowy", skrot="dr test.")
    imp = _imp()
    _analizuj(imp, [_wiersz("Dr. Test")])

    assert not imp.tytuly_do_decyzji.exists()
    row = imp.importpracownikowrow_set.get()
    assert row.tytul_id == t.pk
    assert row.tytul_status == STATUS_TYTUL_TWARDY
    assert row.zrodlo_tytulu_id is None


@pytest.mark.django_db
def test_pusty_tytul_zero_decyzji_bez_statusu():
    imp = _imp()
    _analizuj(imp, [_wiersz("")])

    assert not imp.tytuly_do_decyzji.exists()
    row = imp.importpracownikowrow_set.get()
    assert row.tytul_id is None
    assert row.tytul_status is None  # pusty → bez statusu, bez licznika
    assert row.zrodlo_tytulu_id is None


@pytest.mark.django_db
def test_decyzja_dedup_iexact_dwa_wiersze_jedna_decyzja():
    # ``nazwa_zrodlowa__iexact`` zwija warianty WIELKOŚCI LITER (case-fold),
    # więc dwa wiersze o tym samym tytule w różnym „case” dają JEDNĄ decyzję.
    imp = _imp()
    _analizuj(
        imp,
        [
            _wiersz(NIEDOPASOWANY, nazwisko="Kowalski", row=1),
            _wiersz(NIEDOPASOWANY.upper(), nazwisko="Nowak", row=2),
        ],
    )
    assert imp.tytuly_do_decyzji.count() == 1
    dec = imp.tytuly_do_decyzji.get()
    assert imp.importpracownikowrow_set.filter(zrodlo_tytulu=dec).count() == 2


@pytest.mark.django_db
def test_toggle_off_nie_tworzy_decyzji_brak():
    imp = _imp(tworz_brakujace_tytuly=False)
    _analizuj(imp, [_wiersz(NIEDOPASOWANY)])

    assert not imp.tytuly_do_decyzji.exists()
    row = imp.importpracownikowrow_set.get()
    assert row.tytul_id is None
    assert row.tytul_status == STATUS_TYTUL_BRAK
    assert row.zrodlo_tytulu_id is None


@pytest.mark.django_db
def test_reanaliza_zachowuje_wybor_usera_i_usuwa_stale():
    imp = _imp()
    _analizuj(
        imp,
        [
            _wiersz("Tytul Alfa QAZ", row=1),
            _wiersz("Tytul Beta QAZ", row=2),
        ],
    )
    dec_a = imp.tytuly_do_decyzji.get(nazwa_zrodlowa="Tytul Alfa QAZ")
    dec_a.decyzja = ImportPracownikowTytul.DECYZJA_POMIN
    dec_a.nazwa_do_utworzenia = "Recznie Zmieniony"
    dec_a.skrot_do_utworzenia = "RZ"
    dec_a.save()

    # symuluj on_restart (kasuje wiersze) + re-analizę zmienionego pliku
    imp.importpracownikowrow_set.all().delete()
    _analizuj(
        imp,
        [
            _wiersz("Tytul Alfa QAZ", row=1),
            _wiersz("Tytul Gamma QAZ", row=2),
        ],
    )

    dec_a.refresh_from_db()
    # wybór usera + edytowalne pola ZOSTAJĄ (reconciler odświeża tylko liczone)
    assert dec_a.decyzja == ImportPracownikowTytul.DECYZJA_POMIN
    assert dec_a.nazwa_do_utworzenia == "Recznie Zmieniony"
    assert dec_a.skrot_do_utworzenia == "RZ"
    assert dec_a.tryb == ImportPracownikowTytul.TRYB_BRAK  # liczone, odświeżone

    # „Beta” zniknął z pliku → sprzątnięty; „Gamma” doszedł
    assert not imp.tytuly_do_decyzji.filter(nazwa_zrodlowa="Tytul Beta QAZ").exists()
    assert imp.tytuly_do_decyzji.filter(nazwa_zrodlowa="Tytul Gamma QAZ").exists()
