from unittest.mock import patch

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor_Jednostka, Funkcja_Autora
from import_pracownikow.models import ImportPracownikow
from import_pracownikow.pipeline.analyze import analizuj


def _wiersz(**over):
    base = {
        "nazwisko": "Kowalski",
        "imię": "Jan",
        "nazwa_jednostki": "Katedra Testowa",
        "wydział": "Wydział Testowy",
        "tytuł_stopień": "dr",
        "stanowisko": "Asystent",
        "grupa_pracownicza": "Badawczo-dydaktyczna",
        "data_zatrudnienia": "2016-10-01",
        "wymiar_etatu": "Pełny etat",
        "podstawowe_miejsce_pracy": "TAK",
        "__xls_loc_sheet__": 0,
        "__xls_loc_row__": 7,
    }
    base.update(over)
    return base


@pytest.mark.django_db
def test_analiza_nie_tworzy_slownikow_ani_autor_jednostka(dwa_autory_z_jednostka):
    autor, jednostka = dwa_autory_z_jednostka
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls.name = "protected/import_pracownikow/x.xlsx"

    with patch("import_pracownikow.pipeline.analyze.XLSImportFile") as MockXIF:
        inst = MockXIF.return_value
        inst.count.return_value = 1
        inst.data.return_value = iter(
            [
                _wiersz(
                    nazwisko=autor.nazwisko,
                    imię=autor.imiona,
                    nazwa_jednostki=jednostka.nazwa,
                    stanowisko="NIEISTNIEJACE_STANOWISKO_XYZ",
                )
            ]
        )
        przed = Funkcja_Autora.objects.count()
        analizuj(imp, MockProgress(imp))

    # Faza analizy nie utworzyła nowego stanowiska:
    assert Funkcja_Autora.objects.count() == przed
    row = imp.importpracownikowrow_set.get()
    assert row.funkcja_autora is None
    assert "funkcja_autora" in row.diff_do_utworzenia
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_PRZEANALIZOWANY


@pytest.mark.django_db
def test_analiza_nie_tworzy_autor_jednostka_gdy_brak_powiazania(
    autor_bez_autor_jednostka,
):
    """Autor matchuje się po imieniu+nazwisku mimo braku ``Autor_Jednostka``
    do docelowej jednostki z pliku — analiza (dry-run) NIE tworzy AJ, tylko
    odkłada je do ``diff_do_utworzenia`` (patrz review Task 3: fixture
    ``dwa_autory_z_jednostka`` tworzył AJ z góry, więc gałąź ``aj is None``
    w ``analyze._przetworz_wiersz`` nigdy się nie wykonywała w testach)."""
    autor, jednostka = autor_bez_autor_jednostka
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls.name = "protected/import_pracownikow/x.xlsx"

    with patch("import_pracownikow.pipeline.analyze.XLSImportFile") as MockXIF:
        inst = MockXIF.return_value
        inst.count.return_value = 1
        inst.data.return_value = iter(
            [
                _wiersz(
                    nazwisko=autor.nazwisko,
                    imię=autor.imiona,
                    nazwa_jednostki=jednostka.nazwa,
                )
            ]
        )
        przed = Autor_Jednostka.objects.count()
        analizuj(imp, MockProgress(imp))
    po = Autor_Jednostka.objects.count()

    row = imp.importpracownikowrow_set.get()
    # Warunek wstępny testu: autor MUSI się zmatchować, inaczej test byłby
    # fałszywie zielony na zupełnie innej ścieżce (brak dopasowania autora).
    assert row.autor is not None
    assert row.autor.pk == autor.pk

    # Właściwa asercja: dry-run nie utworzył Autor_Jednostka.
    assert po == przed
    assert row.autor_jednostka is None
    assert row.diff_do_utworzenia["autor_jednostka"] == {
        "autor": autor.pk,
        "jednostka": jednostka.pk,
    }


@pytest.mark.django_db
def test_pusty_plik_rzuca_jawny_blad():
    imp = baker.make(ImportPracownikow)
    imp.plik_xls.name = "protected/import_pracownikow/x.xlsx"
    with patch("import_pracownikow.pipeline.analyze.XLSImportFile") as MockXIF:
        MockXIF.return_value.count.return_value = 0
        MockXIF.return_value.data.return_value = iter([])
        with pytest.raises(ValueError, match="0 wierszy"):
            analizuj(imp, MockProgress(imp))
