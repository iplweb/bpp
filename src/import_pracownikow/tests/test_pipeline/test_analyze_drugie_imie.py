"""Analiza importu pracowników — kolumna „Drugie imię" scalana z „Imię".

Autor ma jedno pole ``imiona``; kolumna ``drugie_imię`` jest doklejana do
``imię`` (np. „Jan" + „Paweł" → „Jan Paweł") PRZED zbudowaniem ``AutorForm``,
więc trafia do ``dane_znormalizowane["imię"]`` i całego downstreamu.
"""

from unittest.mock import patch

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka, Tytul
from import_pracownikow.models import ImportPracownikow
from import_pracownikow.pewnosc import STATUS_ZGADYWANIE
from import_pracownikow.pipeline.analyze import analizuj


def _imp():
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    return imp


def _analizuj_jeden_wiersz(imp, wiersz):
    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MZ:
        MZ.return_value.count.return_value = 1
        MZ.return_value.data.return_value = iter([wiersz])
        analizuj(imp, MockProgress(imp))


@pytest.mark.django_db
def test_drugie_imie_scalane_do_imion():
    jednostka = baker.make(Jednostka, nazwa="Katedra Testowa", skrot="Kat. Test.")
    wiersz = {
        "imię": "Jan",
        "drugie_imię": "Paweł",
        "nazwisko": "Kowalski",
        "nazwa_jednostki": jednostka.nazwa,
        "__xls_loc_sheet__": 0,
        "__xls_loc_row__": 7,
    }
    imp = _imp()
    _analizuj_jeden_wiersz(imp, wiersz)

    row = imp.importpracownikowrow_set.get()
    assert row.dane_znormalizowane["imię"] == "Jan Paweł"
    assert "drugie_imię" not in row.dane_znormalizowane


@pytest.mark.django_db
def test_drugie_imie_matching_po_scaleniu_zachowany():
    # Autor w bazie ma tylko pierwsze imię → strategia „pierwsze imię" (0.95)
    # wiąże go z wierszem mimo scalenia na „Jan Paweł". Dedup zachowany.
    jednostka = baker.make(Jednostka, nazwa="Katedra Testowa", skrot="Kat. Test.")
    autor = baker.make(
        Autor, nazwisko="Kowalski", imiona="Jan", aktualna_jednostka=jednostka
    )
    baker.make(Autor_Jednostka, autor=autor, jednostka=jednostka)
    wiersz = {
        "imię": "Jan",
        "drugie_imię": "Paweł",
        "nazwisko": "Kowalski",
        "nazwa_jednostki": jednostka.nazwa,
        "__xls_loc_sheet__": 0,
        "__xls_loc_row__": 7,
    }
    imp = _imp()
    _analizuj_jeden_wiersz(imp, wiersz)

    row = imp.importpracownikowrow_set.get()
    assert row.autor_id == autor.pk
    # 0.95 (pierwsze imię, nie pełny 1.00) → zgadywanie, ale autor związany.
    assert row.confidence == STATUS_ZGADYWANIE
    assert row.dane_znormalizowane["imię"] == "Jan Paweł"


@pytest.mark.django_db
def test_drugie_imie_scalane_po_rozbiciu_osoby_sklejonej():
    # Regresja kolejności: osoba_sklejona + drugie_imię BEZ kolumny imię.
    # Scalanie MUSI iść PO rozbiciu osoby sklejonej — inaczej „imię" zostałoby
    # ustawione na „Paweł" i parser nie wstawiłby „Jan" z rozbicia.
    jednostka = baker.make(Jednostka, nazwa="Katedra Testowa", skrot="Kat. Test.")
    Tytul.objects.get_or_create(skrot="dr", defaults={"nazwa": "doktor"})
    wiersz = {
        "osoba_sklejona": "dr Jan Kowalski",
        "drugie_imię": "Paweł",
        "nazwa_jednostki": jednostka.nazwa,
        "wydział": "Wydział Testowy",
        "__xls_loc_sheet__": 0,
        "__xls_loc_row__": 7,
    }
    imp = _imp()
    _analizuj_jeden_wiersz(imp, wiersz)

    row = imp.importpracownikowrow_set.get()
    assert row.dane_znormalizowane["nazwisko"] == "Kowalski"
    assert row.dane_znormalizowane["imię"] == "Jan Paweł"
