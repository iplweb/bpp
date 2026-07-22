"""E2E: niedopasowana jednostka przechodzi analizę BEZ crasha (regresja buga
XLSMatchError) i zostaje utworzona w integracji. Spina analizę + integrację."""

from unittest.mock import patch

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowJednostka
from import_pracownikow.pipeline.analyze import analizuj
from import_pracownikow.pipeline.integrate import integruj


@pytest.mark.django_db
def test_e2e_niedopasowana_jednostka_tworzona_bez_crasha(uczelnia):
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    wiersz = {
        "imię": "Jan",
        "nazwisko": "Kowalski",
        "nazwa_jednostki": "Zakład Transfuzjologii",
        "__xls_loc_sheet__": 0,
        "__xls_loc_row__": 1,
    }

    # --- ANALIZA (dawniej: XLSMatchError wywalał cały task) ---
    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MZ:
        MZ.return_value.count.return_value = 1
        MZ.return_value.data.return_value = iter([wiersz])
        analizuj(imp, MockProgress(imp))  # nie rzuca

    assert imp.jednostki_do_decyzji.filter(
        tryb=ImportPracownikowJednostka.TRYB_BRAK,
        nazwa_zrodlowa="Zakład Transfuzjologii",
    ).exists()
    # dry-run: jednostki jeszcze NIE ma w domenie
    assert not Jednostka.objects.filter(nazwa="Zakład Transfuzjologii").exists()

    # --- INTEGRACJA: tworzy jednostkę i podłącza wiersz ---
    imp.stan = ImportPracownikow.STAN_ZATWIERDZONY
    p = MockProgress(imp)
    integruj(imp, p)

    assert p.result_context["utworzono_jednostek"] == 1
    j = Jednostka.objects.get(nazwa="Zakład Transfuzjologii")
    assert j.uczelnia_id == uczelnia.pk
    row = imp.importpracownikowrow_set.get()
    assert row.jednostka_id == j.pk
