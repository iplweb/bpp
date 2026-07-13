from unittest.mock import patch

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor_Jednostka, Funkcja_Autora
from import_common.exceptions import XLSMatchError
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
def test_analiza_nie_tworzy_slownikow_ani_autor_jednostka(
    dwaj_autorzy_z_jednostki, tytuly
):
    autor, jednostka = dwaj_autorzy_z_jednostki
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls.name = "protected/import_pracownikow/x.xlsx"

    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MockZrodlo:
        inst = MockZrodlo.return_value
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
    # Jednostka zmatchowana, brak decyzji o tytułach → analiza przeskakuje Krok 1
    # (struktura już w bazie) i ustawia od razu fazę osób. Dry-run nadal niczego
    # nie utworzył (asercje wyżej) — po prostu nie było co zapisywać.
    assert imp.stan == ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA


@pytest.mark.django_db
def test_analiza_nie_tworzy_autor_jednostka_gdy_brak_powiazania(
    autor_bez_autor_jednostka,
):
    """Autor matchuje się po imieniu+nazwisku mimo braku ``Autor_Jednostka``
    do docelowej jednostki z pliku — analiza (dry-run) NIE tworzy AJ, tylko
    odkłada je do ``diff_do_utworzenia`` (patrz review Task 3: fixture
    ``dwaj_autorzy_z_jednostki`` tworzył AJ z góry, więc gałąź ``aj is None``
    w ``analyze._przetworz_wiersz`` nigdy się nie wykonywała w testach)."""
    autor, jednostka = autor_bez_autor_jednostka
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls.name = "protected/import_pracownikow/x.xlsx"

    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MockZrodlo:
        inst = MockZrodlo.return_value
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
    aj_diff = row.diff_do_utworzenia["autor_jednostka"]
    assert aj_diff["autor"] == autor.pk
    assert aj_diff["jednostka"] == jednostka.pk
    # Pierwsze powiązanie (brak istniejącego AJ) → nie „dodatkowy okres".
    assert aj_diff["nowy_okres"] is False
    # Resolver odkłada też „data od" z pliku (ISO-string / None) do materializacji.
    assert "rozpoczal_prace" in aj_diff


@pytest.mark.django_db
def test_odroczony_create_przy_istniejacym_aj_wymaga_zmian(dwaj_autorzy_z_jednostki):
    # plik MA stanowisko nieistniejące w bazie (odroczony create) + AJ istnieje
    # → wiersz MUSI mieć zmiany_potrzebne=True (bool(diff)), inaczej integracja
    # go pominie i funkcja nigdy nie powstanie (guard is-not-None wyzerował check)
    autor, jednostka = dwaj_autorzy_z_jednostki
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MZ:
        MZ.return_value.count.return_value = 1
        MZ.return_value.data.return_value = iter(
            [
                _wiersz(
                    nazwisko=autor.nazwisko,
                    imię=autor.imiona,
                    nazwa_jednostki=jednostka.nazwa,
                    stanowisko="NIEISTNIEJACE_STANOWISKO_XYZ",
                )
            ]
        )
        analizuj(imp, MockProgress(imp))
    row = imp.importpracownikowrow_set.get()
    assert "funkcja_autora" in row.diff_do_utworzenia
    assert row.zmiany_potrzebne is True


@pytest.mark.django_db
def test_pusty_plik_rzuca_jawny_blad():
    imp = baker.make(ImportPracownikow)
    imp.plik_xls.name = "protected/import_pracownikow/x.xlsx"
    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MockZrodlo:
        MockZrodlo.return_value.count.return_value = 0
        MockZrodlo.return_value.data.return_value = iter([])
        with pytest.raises(ValueError, match="0 wierszy"):
            analizuj(imp, MockProgress(imp))


@pytest.mark.django_db
def test_analiza_scala_podwojny_wymiar_do_kanonicznego(dwa_autory_z_jednostka):
    autor, jednostka = dwa_autory_z_jednostka
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls.name = "protected/import_pracownikow/x.xlsx"
    wiersz = _wiersz(
        nazwisko=autor.nazwisko,
        imię=autor.imiona,
        nazwa_jednostki=jednostka.nazwa,
        wymiar_etatu_tekst="1/2 etatu",
        wymiar_etatu_ulamek="0,5",
    )
    wiersz.pop("wymiar_etatu", None)
    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MockZrodlo:
        inst = MockZrodlo.return_value
        inst.count.return_value = 1
        inst.data.return_value = iter([wiersz])
        analizuj(imp, MockProgress(imp))
    row = imp.importpracownikowrow_set.get()
    # Wymiar zebrany do kanonicznej formy „0,5" (widoczny w znormalizowanych
    # danych wiersza), NIE „1/2 etatu".
    assert row.dane_znormalizowane.get("wymiar_etatu") == "0,5"


@pytest.mark.django_db
def test_analiza_rozbiezny_wymiar_rzuca(dwa_autory_z_jednostka):
    autor, jednostka = dwa_autory_z_jednostka
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls.name = "protected/import_pracownikow/x.xlsx"
    wiersz = _wiersz(
        nazwisko=autor.nazwisko,
        imię=autor.imiona,
        nazwa_jednostki=jednostka.nazwa,
        wymiar_etatu_tekst="1/2 etatu",
        wymiar_etatu_ulamek="1",
    )
    wiersz.pop("wymiar_etatu", None)
    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MockZrodlo:
        inst = MockZrodlo.return_value
        inst.count.return_value = 1
        inst.data.return_value = iter([wiersz])
        with pytest.raises(XLSMatchError):
            analizuj(imp, MockProgress(imp))


@pytest.mark.django_db
def test_analiza_glowny_zaklad_pracy_nie_traktuje_N_jako_prawda(
    dwa_autory_z_jednostka,
):
    # „Gł. zakład pracy" = N → NIE podstawowe miejsce pracy. Pole wiersza liczy
    # normalize_nullboleanfield (poprawnie False); kopia audytowa
    # (dane_znormalizowane) NIE może kłamać True (AutorForm = CharField, nie
    # BooleanField, która „N" koercowała do True).
    autor, jednostka = dwa_autory_z_jednostka
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls.name = "protected/import_pracownikow/x.xlsx"
    wiersz = _wiersz(
        nazwisko=autor.nazwisko,
        imię=autor.imiona,
        nazwa_jednostki=jednostka.nazwa,
        podstawowe_miejsce_pracy="N",
    )
    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MockZrodlo:
        inst = MockZrodlo.return_value
        inst.count.return_value = 1
        inst.data.return_value = iter([wiersz])
        analizuj(imp, MockProgress(imp))
    row = imp.importpracownikowrow_set.get()
    assert row.podstawowe_miejsce_pracy is False
    assert row.dane_znormalizowane.get("podstawowe_miejsce_pracy") is not True
