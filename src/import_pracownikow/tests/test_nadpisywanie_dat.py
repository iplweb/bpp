"""Opcja „Nadpisuj daty zatrudnienia (od/do) wartościami z pliku" —
flaga modelu, bramka zmian, nadpisywanie w integracji, pre-check
nakładania okresów, licznik ostrzeżenia finalizacji (spec
2026-07-26-import-nadpisywanie-dat-zatrudnienia-design.md)."""

from datetime import date

import pytest
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_common.exceptions import BPPDatabaseError
from import_pracownikow.forms import NowyImportForm
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow


@pytest.mark.django_db
def test_flaga_nadpisywania_domyslnie_wylaczona():
    parent = baker.make(ImportPracownikow)
    assert parent.nadpisuj_daty_zatrudnienia is False


def test_formularz_ma_pole_nadpisywania_dat():
    form = NowyImportForm()
    assert "nadpisuj_daty_zatrudnienia" in form.fields
    assert form.fields["nadpisuj_daty_zatrudnienia"].initial in (None, False)


@pytest.mark.django_db
def test_formularz_pole_nadpisywania_w_szufladzie():
    from crispy_forms.utils import render_crispy_form

    html = render_crispy_form(NowyImportForm())
    assert "<details" in html
    pozycja_details = html.index("<details")
    pozycja_pola = html.index("nadpisuj_daty_zatrudnienia")
    assert pozycja_pola > pozycja_details


def _row_z_data(parent, dane, autor, jednostka, aj):
    return baker.make(
        ImportPracownikowRow,
        parent=parent,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        dane_znormalizowane=dane,
        # jak w innych testach tej apki (np. test_stany_pol_materializacja.py):
        # BPPDatabaseError.__str__ woła `self.elem.get(...)` bez guardu na
        # None — bez tego str(exc.value) na ścieżce błędu wywala się
        # AttributeError zamiast dać czytelny komunikat.
        dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": 0},
        # jawnie: `zmiany_potrzebne` to zwykły BooleanField (bez default),
        # baker.make losowałby True/False — a `integrate()` niżej asertuje
        # `self.zmiany_potrzebne` (musi być zdeterminowane, nie flaky).
        zmiany_potrzebne=True,
    )


def _scenariusz_tytulowy(nadpisuj):
    """Otwarty okres od 2026-07-19 (fallback z poprzedniego importu),
    plik niesie 2021-10-01. Jedyna różnica wiersza = data od."""
    parent = baker.make(ImportPracownikow, nadpisuj_daty_zatrudnienia=nadpisuj)
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2026, 7, 19),
        zakonczyl_prace=None,
        podstawowe_miejsce_pracy=True,
    )
    row = _row_z_data(parent, {"data_zatrudnienia": "2021-10-01"}, autor, jednostka, aj)
    return row, aj


@pytest.mark.django_db
def test_bramka_roznica_dat_flaga_on():
    row, _ = _scenariusz_tytulowy(nadpisuj=True)
    assert row.check_if_integration_needed() is True


@pytest.mark.django_db
def test_bramka_roznica_dat_flaga_off_jak_dzis():
    row, _ = _scenariusz_tytulowy(nadpisuj=False)
    assert row.check_if_integration_needed() is False


@pytest.mark.django_db
def test_integracja_nadpisuje_date_od_flaga_on():
    row, aj = _scenariusz_tytulowy(nadpisuj=True)
    row.integrate()
    aj.refresh_from_db()
    assert aj.rozpoczal_prace == date(2021, 10, 1)
    assert any("nadpisano z pliku" in wpis for wpis in row.log_zmian["autor_jednostka"])


@pytest.mark.django_db
def test_integracja_nie_nadpisuje_flaga_off():
    row, aj = _scenariusz_tytulowy(nadpisuj=False)
    # OFF: bramka nie przepuści wiersza; wołamy integrate() wprost, żeby
    # potwierdzić, że nawet wtedy data NIE jest ruszana.
    row.integrate()
    aj.refresh_from_db()
    assert aj.rozpoczal_prace == date(2026, 7, 19)


@pytest.mark.django_db
def test_integracja_nadpisuje_date_do():
    parent = baker.make(ImportPracownikow, nadpisuj_daty_zatrudnienia=True)
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2020, 1, 1),
        zakonczyl_prace=date(2026, 12, 31),
    )
    row = _row_z_data(
        parent,
        {"data_zatrudnienia": "2020-01-01", "data_końca_zatrudnienia": "2024-06-30"},
        autor,
        jednostka,
        aj,
    )
    row.integrate()
    aj.refresh_from_db()
    assert aj.zakonczyl_prace == date(2024, 6, 30)


@pytest.mark.django_db
def test_pusta_komorka_nie_kasuje_daty_przy_on():
    parent = baker.make(ImportPracownikow, nadpisuj_daty_zatrudnienia=True)
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2020, 1, 1),
        zakonczyl_prace=date(2024, 6, 30),
    )
    row = _row_z_data(parent, {}, autor, jednostka, aj)
    row.integrate()
    aj.refresh_from_db()
    assert aj.rozpoczal_prace == date(2020, 1, 1)
    assert aj.zakonczyl_prace == date(2024, 6, 30)


@pytest.mark.django_db
def test_nadpisanie_kolidujace_z_zamknietym_okresem_izolowane():
    # Zamknięty okres 2019-2022 + otwarty od 2026. Plik cofa otwarty na
    # 2021 → przedziały [2021,∞) i [2019-…-2022] nakładają się → błąd
    # izolowany PRZED save (constraint w bazie zatrułby transakcję).
    parent = baker.make(ImportPracownikow, nadpisuj_daty_zatrudnienia=True)
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2019, 1, 1),
        zakonczyl_prace=date(2022, 12, 31),
    )
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2026, 7, 19),
        zakonczyl_prace=None,
    )
    row = _row_z_data(parent, {"data_zatrudnienia": "2021-10-01"}, autor, jednostka, aj)
    with pytest.raises(BPPDatabaseError) as exc:
        row.integrate()
    assert "nakładają się" in str(exc.value)
    aj.refresh_from_db()
    assert aj.rozpoczal_prace == date(2026, 7, 19)  # nic nie zapisano


@pytest.mark.django_db
def test_wypelnienie_null_nie_odpala_precheku():
    # Wypełnienie NULL-a to dzisiejsza ścieżka — bez pre-checku, nawet
    # przy fladze ON (spec §3.4).
    parent = baker.make(ImportPracownikow, nadpisuj_daty_zatrudnienia=True)
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=None,
        zakonczyl_prace=None,
    )
    row = _row_z_data(parent, {"data_zatrudnienia": "2021-10-01"}, autor, jednostka, aj)
    row.integrate()
    aj.refresh_from_db()
    assert aj.rozpoczal_prace == date(2021, 10, 1)


@pytest.mark.django_db
def test_od_wieksze_rowne_do_po_nadpisaniu_odrzucone():
    parent = baker.make(ImportPracownikow, nadpisuj_daty_zatrudnienia=True)
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2020, 1, 1),
        zakonczyl_prace=date(2021, 1, 1),
    )
    row = _row_z_data(parent, {"data_zatrudnienia": "2022-01-01"}, autor, jednostka, aj)
    with pytest.raises(BPPDatabaseError):
        row.integrate()
