# Plik wzorcowy import_pracownikow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zastąpić symlink do fixture'a testowego (`testdata.xlsx`) dedykowanym plikiem wzorcowym importu pracowników, budowanym przez komendę-generator i chronionym testem kontraktowym.

**Architecture:** Komenda zarządzająca `generuj_plik_wzorcowy` buduje `openpyxl.Workbook` (funkcja `zbuduj_workbook()` — źródło prawdy dla treści i formatowania) i zapisuje go do ścieżki static. Symlink zostaje zastąpiony wygenerowaną binarką. Test kontraktowy ładuje binarkę z dysku przez prawdziwą ścieżkę importu (`otworz_zrodlo`) i asertuje, że nagłówek się rozpoznaje, wszystkie kolumny mapują i plik ma dokładnie jeden arkusz z danymi.

**Tech Stack:** Python 3.10+, Django (BaseCommand), openpyxl, pytest.

## Global Constraints

- Max długość linii: 88 znaków (ruff).
- Wszystkie komendy Pythona przez `uv run`. Nigdy gołe `python`/`pytest`.
- NIE modyfikować `testdata.xlsx` ani żadnych testów, które go używają (14 odwołań w 6 plikach).
- Zestaw kolumn: dokładnie te 15 co dziś — bez dodawania/usuwania.
- Zakładka „Opis kolumn" MUSI mieć układ pionowy (nazwy kolumn jedna pod drugą w kolumnie A), inaczej fuzzy-detekcja nagłówka policzy ją jako drugi arkusz danych → `BadNoOfSheetsException`.
- Bez `except: pass` — generator jest offline i deterministyczny, wyjątki propagują.
- Newsfragment: kanoniczny katalog `src/bpp/newsfragments/`, typ `bugfix`.

**15 kolumn (kolejność i brzmienie kanoniczne):**
`Numer`, `Nazwisko`, `Imię`, `ORCID`, `Tytuł/Stopień`, `Stanowisko`, `Grupa pracownicza`, `Nazwa jednostki`, `Wydział`, `Data zatrudnienia`, `Data końca zatrudnienia`, `Podstawowe miejsce pracy`, `PBN UUID`, `BPP ID`, `Wymiar etatu`

(Uwaga: brzmienie oczyszczone — „Data końca zatrudnienia" BEZ końcowej spacji, „Podstawowe miejsce pracy" BEZ `\nTAK/NIE`; podpowiedź „TAK/NIE" idzie w komentarz komórki.)

---

### Task 1: Generator — komenda `generuj_plik_wzorcowy`

Buduje workbook w pamięci (`zbuduj_workbook()`) i zapisuje na dysk (`handle`). Testujemy strukturę workbooka bez IO.

**Files:**
- Create: `src/import_pracownikow/management/commands/generuj_plik_wzorcowy.py`
- Test: `src/import_pracownikow/tests/test_generuj_plik_wzorcowy.py`

**Interfaces:**
- Consumes: nic (openpyxl API).
- Produces:
  - `NAGLOWKI: list[str]` — 15 kanonicznych nagłówków (patrz Global Constraints), w module komendy.
  - `SCIEZKA_DOMYSLNA: str` — absolutna ścieżka do `static/import_pracownikow/import_pracownikow_przyklad.xlsx`.
  - `zbuduj_workbook() -> openpyxl.Workbook` — arkusz „Pracownicy" (nagłówek w wierszu 1, bold + pełna ramka LRTB na 15 komórkach; 4 wiersze przykładowe od wiersza 2) + arkusz „Opis kolumn" (układ pionowy).
  - `Command.handle(**options)` — zapisuje `zbuduj_workbook()` do `options["output"] or SCIEZKA_DOMYSLNA`.

- [ ] **Step 1: Napisz test struktury (failing)**

Utwórz `src/import_pracownikow/tests/test_generuj_plik_wzorcowy.py`:

```python
from import_pracownikow.management.commands.generuj_plik_wzorcowy import (
    NAGLOWKI,
    zbuduj_workbook,
)


def test_naglowki_maja_15_kolumn_i_czyste_brzmienie():
    assert len(NAGLOWKI) == 15
    # Śmieci formatujące nie mogą wrócić:
    for h in NAGLOWKI:
        assert "\n" not in h
        assert h == h.strip()
    assert "Numer" in NAGLOWKI
    assert "Data końca zatrudnienia" in NAGLOWKI
    assert "Podstawowe miejsce pracy" in NAGLOWKI


def test_arkusz_pracownicy_naglowek_w_wierszu_1_z_pelna_ramka():
    wb = zbuduj_workbook()
    ws = wb["Pracownicy"]
    # Nagłówek w wierszu 1:
    wartosci = [ws.cell(row=1, column=c).value for c in range(1, 16)]
    assert wartosci == NAGLOWKI
    # Pełna ramka LRTB na KAŻDEJ komórce nagłówka:
    for c in range(1, 16):
        b = ws.cell(row=1, column=c).border
        assert all(s.style for s in (b.left, b.right, b.top, b.bottom)), (
            f"kolumna {c} nie ma pełnej ramki"
        )
        assert ws.cell(row=1, column=c).font.bold


def test_ma_4_wiersze_przykladowe():
    wb = zbuduj_workbook()
    ws = wb["Pracownicy"]
    # Wiersze 2..5 = dane; kolumna Nazwisko (2) niepusta w każdym:
    for r in range(2, 6):
        assert ws.cell(row=r, column=2).value not in (None, "")


def test_zakladka_opis_kolumn_nie_wpada_w_detekcje_naglowka():
    # Wierny odpowiednik runtime'owej fuzzy-detekcji: normalizujemy KAŻDĄ
    # komórkę i liczymy trafienia w TRY_NAMES. Żaden wiersz nie może mieć
    # ≥ MIN_POINTS trafień — inaczej find_similar_row wziąłby go za nagłówek
    # i „Opis kolumn" policzyłaby się jako drugi arkusz danych.
    from import_common.util import normalize_cell_header
    from import_pracownikow.mapping import MIN_POINTS, TRY_NAMES

    wb = zbuduj_workbook()
    assert "Opis kolumn" in wb.sheetnames
    ws = wb["Opis kolumn"]
    zbior = set(TRY_NAMES)
    for row in ws.iter_rows(values_only=True):
        trafienia = sum(
            1 for v in row if v is not None and normalize_cell_header(v) in zbior
        )
        assert trafienia < MIN_POINTS, f"wiersz wygląda jak nagłówek: {row}"
```

- [ ] **Step 2: Uruchom test — ma FAILOWAĆ (brak modułu)**

Run: `uv run pytest src/import_pracownikow/tests/test_generuj_plik_wzorcowy.py -v`
Expected: FAIL — `ModuleNotFoundError` / `ImportError` (komenda nie istnieje).

- [ ] **Step 3: Napisz generator**

Utwórz `src/import_pracownikow/management/commands/generuj_plik_wzorcowy.py`:

```python
"""Generator pliku wzorcowego importu pracowników.

Źródło prawdy dla treści i formatowania pliku, który użytkownik pobiera
przyciskiem „pobierz plik wzorcowy". Regeneracja:

    uv run python src/manage.py generuj_plik_wzorcowy

Zapisuje do ``static/import_pracownikow/import_pracownikow_przyklad.xlsx``.
Ten plik jest ZACOMMITOWANĄ binarką (nie generuje się w runtime) — po każdej
zmianie generatora trzeba go zregenerować i zacommitować.
"""

import os

from django.core.management.base import BaseCommand
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Border, Font, Side

import import_pracownikow

# 15 kanonicznych nagłówków — brzmienie oczyszczone ze śmieci formatujących
# (bez końcowej spacji, bez „\n"). Mapują się 1:1 na pola docelowe importu
# (patrz import_pracownikow.mapping._SYNONIMY). Kolejność = kolejność kolumn.
NAGLOWKI = [
    "Numer",
    "Nazwisko",
    "Imię",
    "ORCID",
    "Tytuł/Stopień",
    "Stanowisko",
    "Grupa pracownicza",
    "Nazwa jednostki",
    "Wydział",
    "Data zatrudnienia",
    "Data końca zatrudnienia",
    "Podstawowe miejsce pracy",
    "PBN UUID",
    "BPP ID",
    "Wymiar etatu",
]

# Podpowiedzi w komentarzach komórek nagłówka (klucz = nagłówek).
_KOMENTARZE = {
    "Numer": "Numer ID pracownika z systemu kadrowego (opcjonalny).",
    "Podstawowe miejsce pracy": "Wpisz TAK lub NIE.",
    "PBN UUID": "Identyfikator użytkownika w systemie PBN (opcjonalny).",
    "BPP ID": "Numer ID w Bazie Publikacji Pracowników (opcjonalny).",
}

# 4 wiersze przykładowe — różne przypadki (patrz spec). None = pusta komórka.
# Kolejność wartości odpowiada NAGLOWKI.
_WIERSZE = [
    # pełny etat, zatrudnienie trwa
    [9530, "Kowalski", "Jan", None, "lek. med.", "Asystent",
     "Badawczo-dydaktyczna",
     "Katedra i Klinika Dermatologii", "Wydział Lekarski",
     "2016-10-01", None, "TAK", None, None, "Pełny etat"],
    # część etatu
    [9531, "Nowak", "Maria", "0000-0002-2752-5144", "dr n. med.", "Adiunkt",
     "Dydaktyczna", "Katedra Testowa", "Wydział Lekarski",
     "2018-02-01", None, "NIE", None, None, "1/2 etatu"],
    # zatrudnienie zakończone
    [9532, "Wiśniewski", "Adam", None, "prof. dr hab.", "Profesor",
     "Badawczo-dydaktyczna", "Katedra Testowa", "Wydział Lekarski",
     "2005-10-01", "2020-09-30", "TAK", None, None, "Pełny etat"],
    # minimum danych (bez ORCID/PBN/BPP ID)
    [None, "Lubelska", "Anna", None, None, None,
     None, "Katedra Testowa", None,
     None, None, None, None, None, None],
]

# Zakładka „Opis kolumn" — układ PIONOWY (nazwa | znaczenie | wymagana?).
# Nazwy kolumn jedna pod drugą w kolumnie A — NIGDY ≥2 nazwy w jednym wierszu,
# inaczej find_similar_row wziąłby to za nagłówek i policzył jako drugi arkusz
# danych (→ BadNoOfSheetsException). Chroni to test kontraktowy (Task 2).
_OPIS = [
    ("Numer", "ID z systemu kadrowego", "opcjonalna"),
    ("Nazwisko", "Nazwisko pracownika", "wymagana"),
    ("Imię", "Imię pracownika", "wymagana"),
    ("ORCID", "Identyfikator ORCID", "opcjonalna"),
    ("Tytuł/Stopień", "Tytuł lub stopień naukowy (np. dr, prof.)", "opcjonalna"),
    # UWAGA: opis NIE może po normalizacji dać dokładnego synonimu z
    # _SYNONIMY (np. „funkcja w jednostce" → funkcja_w_jednostce), bo razem
    # z nazwą w kolumnie A dałby 2 trafienia → wiersz wzięty za nagłówek.
    ("Stanowisko", "Nazwa stanowiska/funkcji", "opcjonalna"),
    ("Grupa pracownicza", "Np. badawczo-dydaktyczna", "opcjonalna"),
    ("Nazwa jednostki", "Pełna nazwa jednostki organizacyjnej", "wymagana"),
    ("Wydział", "Nazwa wydziału", "opcjonalna"),
    ("Data zatrudnienia", "Format RRRR-MM-DD", "opcjonalna"),
    ("Data końca zatrudnienia", "Format RRRR-MM-DD; puste = trwa", "opcjonalna"),
    ("Podstawowe miejsce pracy", "TAK lub NIE", "opcjonalna"),
    ("PBN UUID", "Identyfikator użytkownika w PBN", "opcjonalna"),
    ("BPP ID", "ID w Bazie Publikacji Pracowników", "opcjonalna"),
    ("Wymiar etatu", "Np. Pełny etat, 1/2 etatu", "opcjonalna"),
]

SCIEZKA_DOMYSLNA = os.path.join(
    os.path.dirname(import_pracownikow.__file__),
    "static",
    "import_pracownikow",
    "import_pracownikow_przyklad.xlsx",
)

_RAMKA = Border(*(Side(style="thin") for _ in range(4)))


def zbuduj_workbook() -> Workbook:
    """Buduje workbook pliku wzorcowego (arkusz danych + zakładka opisu)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Pracownicy"

    for col, naglowek in enumerate(NAGLOWKI, start=1):
        cell = ws.cell(row=1, column=col, value=naglowek)
        cell.font = Font(bold=True)
        cell.border = _RAMKA
        if naglowek in _KOMENTARZE:
            cell.comment = Comment(_KOMENTARZE[naglowek], "BPP")

    for r, wiersz in enumerate(_WIERSZE, start=2):
        for c, wartosc in enumerate(wiersz, start=1):
            ws.cell(row=r, column=c, value=wartosc)

    ws.column_dimensions["H"].width = 41

    opis = wb.create_sheet("Opis kolumn")
    opis.cell(row=1, column=1, value="Kolumna").font = Font(bold=True)
    opis.cell(row=1, column=2, value="Znaczenie").font = Font(bold=True)
    opis.cell(row=1, column=3, value="Wymagana?").font = Font(bold=True)
    for r, (nazwa, znaczenie, wym) in enumerate(_OPIS, start=2):
        opis.cell(row=r, column=1, value=nazwa)
        opis.cell(row=r, column=2, value=znaczenie)
        opis.cell(row=r, column=3, value=wym)
    opis.column_dimensions["A"].width = 26
    opis.column_dimensions["B"].width = 44

    return wb


class Command(BaseCommand):
    help = "Generuje plik wzorcowy importu pracowników (XLSX)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default=None,
            help="Ścieżka wyjściowa (domyślnie: plik static pliku wzorcowego).",
        )

    def handle(self, *args, **options):
        sciezka = options["output"] or SCIEZKA_DOMYSLNA
        zbuduj_workbook().save(sciezka)
        self.stdout.write(f"Zapisano plik wzorcowy: {sciezka}")
```

- [ ] **Step 4: Uruchom test — ma PRZEJŚĆ**

Run: `uv run pytest src/import_pracownikow/tests/test_generuj_plik_wzorcowy.py -v`
Expected: PASS (4 testy).

- [ ] **Step 5: Sprawdź brzmienie i format (ruff)**

Run: `ruff format src/import_pracownikow/management/commands/generuj_plik_wzorcowy.py src/import_pracownikow/tests/test_generuj_plik_wzorcowy.py && ruff check src/import_pracownikow/management/commands/generuj_plik_wzorcowy.py src/import_pracownikow/tests/test_generuj_plik_wzorcowy.py`
Expected: brak błędów.

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/management/commands/generuj_plik_wzorcowy.py \
        src/import_pracownikow/tests/test_generuj_plik_wzorcowy.py
git commit -m "feat(import_pracownikow): generator pliku wzorcowego (XLSX)"
```

---

### Task 2: Zastąp symlink binarką + test kontraktowy + newsfragment

Uruchamia generator, zastępuje symlink prawdziwym plikiem, dokłada test kontraktowy (prawdziwa ścieżka importu) i newsfragment.

**Files:**
- Delete (symlink) + Create (binarka): `src/import_pracownikow/static/import_pracownikow/import_pracownikow_przyklad.xlsx`
- Create: `src/import_pracownikow/tests/test_plik_wzorcowy.py`
- Create: `src/bpp/newsfragments/import_pracownikow.bugfix.rst`

**Interfaces:**
- Consumes: `zbuduj_workbook`, `SCIEZKA_DOMYSLNA` z Task 1; `otworz_zrodlo` (`import_common.sources`); `TRY_NAMES`, `MIN_POINTS`, `zaproponuj_mapowanie`, `waliduj_mapowanie`, `POLE_POMIN`, `sprawdz_pojedynczy_arkusz` (`import_pracownikow.mapping`).
- Produces: zacommitowana binarka pobierana przez przycisk „pobierz plik wzorcowy".

- [ ] **Step 1: Napisz test kontraktowy (failing — plik to jeszcze symlink do surowego fixture'a)**

Utwórz `src/import_pracownikow/tests/test_plik_wzorcowy.py`:

```python
import os

from import_common.sources import otworz_zrodlo
from import_pracownikow.management.commands.generuj_plik_wzorcowy import (
    SCIEZKA_DOMYSLNA,
)
from import_pracownikow.mapping import (
    MIN_POINTS,
    POLE_POMIN,
    TRY_NAMES,
    sprawdz_pojedynczy_arkusz,
    waliduj_mapowanie,
    zaproponuj_mapowanie,
)

_LOC = ("__xls_loc_sheet__", "__xls_loc_row__")


def _naglowki_ze_zrodla(zrodlo):
    pierwszy = next(iter(zrodlo.data()))
    return [k for k in pierwszy.keys() if k not in _LOC]


def test_plik_wzorcowy_nie_jest_symlinkiem():
    # Rozdzielenie od fixture'a testowego (testdata.xlsx) musi się utrzymać.
    assert not os.path.islink(SCIEZKA_DOMYSLNA)


def test_plik_wzorcowy_ma_dokladnie_jeden_arkusz_z_danymi():
    # Zakładka „Opis kolumn" NIE może wpaść w fuzzy-detekcję nagłówka
    # (inaczej sprawdz_pojedynczy_arkusz podniósłby BadNoOfSheetsException).
    zrodlo = otworz_zrodlo(
        SCIEZKA_DOMYSLNA, try_names=TRY_NAMES, min_points=MIN_POINTS
    )
    assert zrodlo.liczba_arkuszy_z_danymi() == 1
    sprawdz_pojedynczy_arkusz(zrodlo)  # nie podnosi wyjątku


def test_plik_wzorcowy_mapuje_wszystkie_kolumny():
    zrodlo = otworz_zrodlo(
        SCIEZKA_DOMYSLNA, try_names=TRY_NAMES, min_points=MIN_POINTS
    )
    naglowki = _naglowki_ze_zrodla(zrodlo)
    mapowanie = zaproponuj_mapowanie(naglowki)
    assert POLE_POMIN not in mapowanie.values(), (
        f"nierozpoznane kolumny: "
        f"{[h for h, c in mapowanie.items() if c == POLE_POMIN]}"
    )


def test_plik_wzorcowy_przechodzi_walidacje_mapowania():
    zrodlo = otworz_zrodlo(
        SCIEZKA_DOMYSLNA, try_names=TRY_NAMES, min_points=MIN_POINTS
    )
    naglowki = _naglowki_ze_zrodla(zrodlo)
    mapowanie = zaproponuj_mapowanie(naglowki)
    assert waliduj_mapowanie(mapowanie) == []


def test_naglowki_bez_smieci_formatujacych():
    zrodlo = otworz_zrodlo(
        SCIEZKA_DOMYSLNA, try_names=TRY_NAMES, min_points=MIN_POINTS
    )
    # Nagłówki są znormalizowane w źródle; sprawdzamy surowe komórki wprost.
    import openpyxl

    ws = openpyxl.load_workbook(SCIEZKA_DOMYSLNA)["Pracownicy"]
    surowe = [ws.cell(row=1, column=c).value for c in range(1, 16)]
    for h in surowe:
        assert "\n" not in h
        assert h == h.strip()
```

- [ ] **Step 2: Uruchom test — ma FAILOWAĆ**

Run: `uv run pytest src/import_pracownikow/tests/test_plik_wzorcowy.py -v`
Expected: FAIL — `test_plik_wzorcowy_nie_jest_symlinkiem` (plik to symlink) oraz `test_..._jeden_arkusz` / `test_naglowki_bez_smieci` (surowy fixture ma nagłówek w wierszu 7, śmieci formatujące, brak zakładki).

- [ ] **Step 3: Usuń symlink i wygeneruj binarkę**

```bash
rm src/import_pracownikow/static/import_pracownikow/import_pracownikow_przyklad.xlsx
uv run python src/manage.py generuj_plik_wzorcowy
```

Sprawdź, że powstał prawdziwy plik (nie symlink):

Run: `ls -la src/import_pracownikow/static/import_pracownikow/import_pracownikow_przyklad.xlsx`
Expected: zwykły plik (bez `->` w wydruku), rozmiar > 0.

- [ ] **Step 4: Uruchom test kontraktowy — ma PRZEJŚĆ**

Run: `uv run pytest src/import_pracownikow/tests/test_plik_wzorcowy.py -v`
Expected: PASS (5 testów).

- [ ] **Step 5: Dodaj newsfragment**

Utwórz `src/bpp/newsfragments/import_pracownikow.bugfix.rst`:

```rst
Poprawiono plik wzorcowy importu pracowników (kompletna ramka, przykładowe
wiersze, opis kolumn); rozdzielono go od danych testowych.
```

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/static/import_pracownikow/import_pracownikow_przyklad.xlsx \
        src/import_pracownikow/tests/test_plik_wzorcowy.py \
        src/bpp/newsfragments/import_pracownikow.bugfix.rst
git commit -m "fix(import_pracownikow): dedykowany plik wzorcowy zamiast symlinku do fixture'a

Symlink import_pracownikow_przyklad.xlsx -> tests/testdata.xlsx serwował
klientom surowy fixture testowy (niekompletna ramka, jeden wiersz). Teraz
plik wzorcowy jest produktem komendy generuj_plik_wzorcowy, a test
kontraktowy pilnuje, że przechodzi własny import."
```

---

### Task 3: Weryfikacja końcowa

- [ ] **Step 1: Cała sekcja testów importu pracowników**

Run: `uv run pytest src/import_pracownikow/tests/test_plik_wzorcowy.py src/import_pracownikow/tests/test_generuj_plik_wzorcowy.py -v`
Expected: wszystkie PASS.

- [ ] **Step 2: Testy używające testdata.xlsx nie ucierpiały**

Run: `uv run pytest src/import_pracownikow/tests/ -q`
Expected: brak nowych failów (fixture nietknięty).

- [ ] **Step 3: pre-commit na zmienionych plikach**

Run: `pre-commit run --files src/import_pracownikow/management/commands/generuj_plik_wzorcowy.py src/import_pracownikow/tests/test_plik_wzorcowy.py src/import_pracownikow/tests/test_generuj_plik_wzorcowy.py src/bpp/newsfragments/import_pracownikow.bugfix.rst`
Expected: PASS (bez argumentów-hacków; ewentualne uwagi poprawiane ręcznie Edit-em, nie `--fix`).

- [ ] **Step 4: Wizualna kontrola pliku (opcjonalna, zalecana)**

Otwórz wygenerowany plik i potwierdź wizualnie: nagłówek w wierszu 1 z pełną ramką, 4 wiersze przykładowe, zakładka „Opis kolumn". (Można też przez `run-site` pobrać plik przyciskiem i obejrzeć.)

---

## Self-Review

**Spec coverage:**
- Rozdzielenie od fixture'a (usunięcie symlinku) → Task 2 Step 3 + test `nie_jest_symlinkiem`. ✓
- 15 kolumn, brzmienie oczyszczone → Task 1 `NAGLOWKI` + testy śmieci. ✓
- Nagłówek w wierszu 1 + ramka + 4 wiersze → Task 1 `zbuduj_workbook` + testy. ✓
- Komentarze komórek + zakładka „Opis kolumn" pionowa → Task 1 `_KOMENTARZE`/`_OPIS` + test układu pionowego. ✓
- Generator w repo + binarka + test kontraktowy → Task 1 + Task 2. ✓
- Reguła „jeden arkusz z danymi" (`liczba_arkuszy_z_danymi() == 1`) → Task 2 test. ✓
- Test kontraktowy: detekcja nagłówka + mapowanie bez POLE_POMIN + walidacja pusta → Task 2 testy. ✓
- Newsfragment bugfix → Task 2 Step 5. ✓
- Obsługa błędów (wyjątki propagują, bez except: pass) → generator nie łapie wyjątków. ✓

**Placeholder scan:** brak TBD/TODO; cały kod generatora i testów jest kompletny. ✓

**Type consistency:** `zbuduj_workbook`, `NAGLOWKI`, `SCIEZKA_DOMYSLNA` używane w Task 2 zgodnie z definicją w Task 1. `otworz_zrodlo(path, try_names=, min_points=)` i `liczba_arkuszy_z_danymi()` zgodne z `import_common/sources.py`. Ekstrakcja nagłówków (`k not in _LOC`) zgodna z `naglowki_i_probka` (`models.py:388`). ✓
