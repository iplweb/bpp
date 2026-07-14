from io import BytesIO

import pytest
from model_bakery import baker
from openpyxl import load_workbook

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.eksport import zbuduj_plik_po_imporcie
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.tests._helpers import unikalna_nazwa


def _wczytaj(content):
    ws = load_workbook(BytesIO(content)).active
    naglowki = [c.value for c in ws[1]]
    wiersze = [[c.value for c in row] for row in ws.iter_rows(min_row=2)]
    return naglowki, wiersze


def _import_zintegrowany(**kw):
    return baker.make(
        ImportPracownikow,
        stan=ImportPracownikow.STAN_ZINTEGROWANY,
        mapowanie_kolumn=kw.pop("mapowanie_kolumn", {}),
        **kw,
    )


def _wiersz(imp, *, loc, autor=None, autor_jednostka=None, dane=None):
    return baker.make(
        ImportPracownikowRow,
        parent=imp,
        autor=autor,
        autor_jednostka=autor_jednostka,
        zmiany_potrzebne=False,
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": loc, **(dane or {})},
    )


@pytest.mark.django_db
def test_builder_pomija_wiersze_bez_autora_i_zachowuje_kolejnosc():
    imp = _import_zintegrowany(
        mapowanie_kolumn={
            "Nazwisko": "nazwisko",
            "Imię": "imię",
            "Jednostka": "nazwa_jednostki",
        }
    )
    j = baker.make(Jednostka, nazwa=unikalna_nazwa("Klinika Poprawna"))
    a2 = baker.make(Autor, nazwisko="Druga", imiona="Anna")
    aj2 = baker.make(Autor_Jednostka, autor=a2, jednostka=j)
    a1 = baker.make(Autor, nazwisko="Pierwszy", imiona="Jan")
    aj1 = baker.make(Autor_Jednostka, autor=a1, jednostka=j)
    # loc rosnąco: a1 (loc=0), a2 (loc=1); wiersz pominięty (loc=2, autor=None)
    _wiersz(imp, loc=0, autor=a1, autor_jednostka=aj1)
    _wiersz(imp, loc=1, autor=a2, autor_jednostka=aj2)
    _wiersz(imp, loc=2, autor=None, autor_jednostka=None)

    naglowki, wiersze = _wczytaj(zbuduj_plik_po_imporcie(imp))

    assert len(wiersze) == 2  # pominięty wypadł
    assert naglowki[:4] == ["BPP ID", "Nazwisko", "Imię", "Nazwa jednostki"]
    assert [w[0] for w in wiersze] == [a1.pk, a2.pk]  # kolejność z pliku
    assert [w[1] for w in wiersze] == ["Pierwszy", "Druga"]
