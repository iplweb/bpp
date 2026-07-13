"""E2E rozpoznania kolumn wykazu 2026 na SYNTETYCZNYM pliku (dane wymyślone —
RODO). Sprawdza cały łańcuch: realny XLSX → auto-mapowanie nagłówków
(``Data od``/``Data do``/``Gł. zakład pracy``/podwójny ``Wymiar etatu``) →
``analizuj`` → rozpoznane pola na wierszu, z wymiarem sprowadzonym do
kanonicznej formy."""

from unittest.mock import patch

import openpyxl
import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from import_common.sources import otworz_zrodlo as _real_otworz_zrodlo
from import_pracownikow.mapping import MIN_POINTS, TRY_NAMES, zaproponuj_mapowanie
from import_pracownikow.models import ImportPracownikow
from import_pracownikow.pipeline.analyze import analizuj

# Nagłówki dokładnie jak w prawdziwym „wykaz 2026.xlsx" (dane w teście
# SYNTETYCZNE — kolumna 3 pusta jak w oryginale, dwa identyczne „Wymiar etatu").
_NAGLOWKI = [
    "Lp.",
    "NUMER",
    None,
    "Nazwisko",
    "Imię ",
    "Tytuł/ Stopień",
    "Stanowisko",
    "Grupa pracownicza",
    "Nazwa jednostki",
    "Wydział",
    "Data od",
    "Gł. zakład pracy",
    "Wymiar etatu",
    "Wymiar etatu",
    "Data do",
]


def _zapisz_wykaz(path, autor, jednostka):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "30.06.2026"
    ws.append(_NAGLOWKI)
    ws.append(
        [
            1,
            1000,
            None,
            autor.nazwisko,
            autor.imiona,
            "dr",
            "Adiunkt",
            "Badawcza",
            jednostka.nazwa,
            "Wydział Testowy",
            "2020-01-01",
            "T",
            "1/2 etatu",
            "0,5",
            "2025-12-31",
        ]
    )
    wb.save(path)


def _naglowki_pliku(path):
    zrodlo = _real_otworz_zrodlo(path, try_names=TRY_NAMES, min_points=MIN_POINTS)
    wiersz = next(iter(zrodlo.data()))
    return [k for k in wiersz if k not in ("__xls_loc_sheet__", "__xls_loc_row__")]


@pytest.mark.django_db
def test_wykaz_rozpoznaje_daty_glowny_zaklad_i_wymiar(dwa_autory_z_jednostka, tmp_path):
    autor, jednostka = dwa_autory_z_jednostka
    plik = str(tmp_path / "wykaz.xlsx")
    _zapisz_wykaz(plik, autor, jednostka)

    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls.name = "protected/import_pracownikow/wykaz.xlsx"
    # Auto-mapowanie z realnych nagłówków pliku (jak ekran mapowania):
    imp.mapowanie_kolumn = zaproponuj_mapowanie(_naglowki_pliku(plik))
    imp.save()

    # analizuj czyta parent.plik_xls.path (storage) — kierujemy je na plik
    # tymczasowy, otwierając realne źródło (bez podmieniania storage).
    def _otworz_z_tmp(_sciezka_storage, **kw):
        return _real_otworz_zrodlo(plik, **kw)

    with patch(
        "import_pracownikow.pipeline.analyze.otworz_zrodlo",
        side_effect=_otworz_z_tmp,
    ):
        analizuj(imp, MockProgress(imp))

    row = imp.importpracownikowrow_set.get()
    dane = row.dane_znormalizowane
    # „Data od" rozpoznane jako data zatrudnienia (ISO sparsowane do daty):
    assert dane.get("data_zatrudnienia")
    # „Data do" rozpoznane jako data końca zatrudnienia:
    assert dane.get("data_końca_zatrudnienia")
    # Podwójny „Wymiar etatu" (tekst „1/2 etatu" + ułamek „0,5") → kanoniczny:
    assert dane.get("wymiar_etatu") == "0,5"
    # „Gł. zakład pracy" = T → podstawowe miejsce pracy = prawda (pole wiersza
    # liczone z normalize_nullboleanfield, spójne z integracją):
    assert row.podstawowe_miejsce_pracy is True
    # Autor zmatchowany po nazwisku+imieniu:
    assert row.autor == autor
