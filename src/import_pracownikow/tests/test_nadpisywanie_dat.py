"""Opcja „Nadpisuj daty zatrudnienia (od/do) wartościami z pliku" —
flaga modelu, bramka zmian, nadpisywanie w integracji, pre-check
nakładania okresów, licznik ostrzeżenia finalizacji (spec
2026-07-26-import-nadpisywanie-dat-zatrudnienia-design.md)."""

import re
from datetime import date

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_common.exceptions import BPPDatabaseError
from import_pracownikow.forms import NowyImportForm
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pipeline.integrate import (
    _integruj_wiersz,
    _oznacz_wiersz_bledny,
)


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
def test_nakladanie_wspolny_dzien_koliduje():
    # Granica przedziałów DOMKNIĘTYCH (_sprawdz_nakladanie_okresow lustrzy
    # DATERANGE(..., '[]') z bpp/models/autor.py): inny okres zamknięty
    # kończy się DOKŁADNIE w dniu, na który plik nadpisuje początek innego
    # okresu → [2019-01-01, 2021-10-01] i [2021-10-01, ∞) dzielą wspólny
    # dzień → kolidują (odwrotnie niż „dzień po końcu" niżej).
    parent = baker.make(ImportPracownikow, nadpisuj_daty_zatrudnienia=True)
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2019, 1, 1),
        zakonczyl_prace=date(2021, 10, 1),
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
def test_nakladanie_dzien_po_koncu_nie_koliduje():
    # Dzień PO końcu innego zamkniętego okresu — przedziały domknięte
    # [2019-01-01, 2021-09-30] i [2021-10-01, ∞) SĄSIADUJĄ, ale się nie
    # nakładają → brak kolizji, nadpisanie przechodzi.
    parent = baker.make(ImportPracownikow, nadpisuj_daty_zatrudnienia=True)
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2019, 1, 1),
        zakonczyl_prace=date(2021, 9, 30),
    )
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2026, 7, 19),
        zakonczyl_prace=None,
    )
    row = _row_z_data(parent, {"data_zatrudnienia": "2021-10-01"}, autor, jednostka, aj)
    row.integrate()
    aj.refresh_from_db()
    assert aj.rozpoczal_prace == date(2021, 10, 1)


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


@pytest.mark.django_db
def test_liczba_nadpisan_dat_liczy_tylko_realne_nadpisania():
    parent = baker.make(ImportPracownikow, nadpisuj_daty_zatrudnienia=True)
    autor1, autor2, autor3 = baker.make(Autor), baker.make(Autor), baker.make(Autor)
    jednostka = baker.make(Jednostka)
    # 1) realne nadpisanie: baza 2026, plik 2021 → LICZY SIĘ
    aj1 = baker.make(
        Autor_Jednostka,
        autor=autor1,
        jednostka=jednostka,
        rozpoczal_prace=date(2026, 7, 19),
    )
    _row_z_data(parent, {"data_zatrudnienia": "2021-10-01"}, autor1, jednostka, aj1)
    # 2) wypełnienie NULL-a → NIE liczy się
    aj2 = baker.make(
        Autor_Jednostka, autor=autor2, jednostka=jednostka, rozpoczal_prace=None
    )
    _row_z_data(parent, {"data_zatrudnienia": "2021-10-01"}, autor2, jednostka, aj2)
    # 3) zgodne daty → NIE liczy się
    aj3 = baker.make(
        Autor_Jednostka,
        autor=autor3,
        jednostka=jednostka,
        rozpoczal_prace=date(2021, 10, 1),
    )
    _row_z_data(parent, {"data_zatrudnienia": "2021-10-01"}, autor3, jednostka, aj3)
    assert parent.liczba_nadpisan_dat() == 1


@pytest.mark.django_db
def test_liczba_nadpisan_dat_zero_przy_fladze_off():
    parent = baker.make(ImportPracownikow, nadpisuj_daty_zatrudnienia=False)
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2026, 7, 19),
    )
    _row_z_data(parent, {"data_zatrudnienia": "2021-10-01"}, autor, jednostka, aj)
    assert parent.liczba_nadpisan_dat() == 0


def _przeglad_url(parent):
    return reverse("import_pracownikow:przeglad", kwargs={"pk": parent.pk})


def _parent_faza_osob_z_nadpisaniem(owner, nadpisuj):
    """Parent w stanie fazy osób (Krok 2 — struktura już zapisana) + 1
    wiersz z realnym nadpisaniem (baza 2026-07-19, plik 2021-10-01), jak
    w ``test_liczba_nadpisan_dat_liczy_tylko_realne_nadpisania``."""
    parent = baker.make(
        ImportPracownikow,
        owner=owner,
        stan=ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA,
        nadpisuj_daty_zatrudnienia=nadpisuj,
    )
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2026, 7, 19),
    )
    _row_z_data(parent, {"data_zatrudnienia": "2021-10-01"}, autor, jednostka, aj)
    return parent


@pytest.mark.django_db
def test_przeglad_callout_nadpisywania_widoczny_przy_on(admin_client, admin_user):
    parent = _parent_faza_osob_z_nadpisaniem(admin_user, nadpisuj=True)
    resp = admin_client.get(_przeglad_url(parent))
    html = resp.content.decode("utf-8")
    assert "Włączono nadpisywanie dat zatrudnienia" in html
    # NADPISANE musi być w confirm-owym onsubmit formularza zapisu osób —
    # nie wystarczy, że jest gdzieś na stronie (np. sam callout).
    match = re.search(r'onsubmit="([^"]*)"', html)
    assert match is not None
    assert "NADPISANE" in match.group(1)


@pytest.mark.django_db
def test_przeglad_bez_calloutu_przy_off(admin_client, admin_user):
    parent = _parent_faza_osob_z_nadpisaniem(admin_user, nadpisuj=False)
    resp = admin_client.get(_przeglad_url(parent))
    html = resp.content.decode("utf-8")
    assert "Włączono nadpisywanie dat zatrudnienia" not in html


# Testy e2e przez pipeline'owy `_integruj_wiersz` (pipeline/integrate.py) —
# w odróżnieniu od testów wyżej, które wołają `row.integrate()` wprost, te
# przechodzą też przez świeży re-check (integrate.py ~L227), zamrożenie
# `stany_pol_snapshot` PRZED materializacją i (w scenariuszu kolizji) tę samą
# izolację per-wiersz co pętla integracji w `integruj()` (~L1005-1013).


def _integruj_wiersz_izolowany(row):
    """Odbicie pętli integracji w ``integruj()`` (pipeline/integrate.py
    ~L1005-1013): łapie ``BPPDatabaseError`` per-wiersz i oznacza wiersz
    ``_oznacz_wiersz_bledny`` — DOKŁADNIE tak, jak robi to prawdziwy
    pipeline, żeby błąd JEDNEGO wiersza nie wywalił całej integracji."""
    try:
        return _integruj_wiersz(row)
    except BPPDatabaseError as e:
        _oznacz_wiersz_bledny(row, e.reason)
        return None


@pytest.mark.django_db
def test_integruj_wiersz_scenariusz_tytulowy_nadpisuje_przez_pipeline():
    """Spec §3.6 pkt 2: pełna ścieżka pipeline'u (nie sam
    ``row.integrate()``) nadpisuje datę i NIE oznacza wiersza fałszywie
    ``pominiety_bo_nieaktualny`` (świeży re-check widzi realną potrzebę
    zmiany, więc bierze normalną gałąź integracji, nie gałąź driftu)."""
    row, aj = _scenariusz_tytulowy(nadpisuj=True)
    wynik = _integruj_wiersz(row)
    assert wynik is False  # to NIE jest nowy okres — istniejący AJ
    aj.refresh_from_db()
    row.refresh_from_db()
    assert aj.rozpoczal_prace == date(2021, 10, 1)
    assert row.pominiety_bo_nieaktualny is False


@pytest.mark.django_db
def test_integruj_wiersz_kolizja_izolowana_oznacza_wiersz_bledny():
    """Kolizja z zamkniętym okresem przechodząca przez ``_integruj_wiersz``
    + izolację pętli integracji (``_integruj_wiersz_izolowany`` wyżej):
    błąd JEDNEGO wiersza NIE propaguje się na zewnątrz (per-wiersz
    izolacja), wiersz zostaje oznaczony ``log_zmian["blad"]`` przez
    ``_oznacz_wiersz_bledny``, a data AJ zostaje nietknięta."""
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
    wynik = _integruj_wiersz_izolowany(row)  # nie podnosi — izolacja
    assert wynik is None
    row.refresh_from_db()
    assert "nakładają się" in row.log_zmian["blad"][0]
    aj.refresh_from_db()
    assert aj.rozpoczal_prace == date(2026, 7, 19)  # nic nie zapisano
