# Import — rozpoznawanie kolumn wykazu (Data od/do, Gł. zakład pracy, podwójny wymiar etatu) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sprawić, by plik `wykaz 2026.xlsx` (i pliki o tym układzie nagłówków)
mapował się automatycznie: `Data od`/`Data do` → daty kadrowe, `Gł. zakład pracy`
(T/N) → podstawowe miejsce pracy, podwójny `Wymiar etatu` (tekst + ułamek) →
kanoniczny ułamek walidowany krzyżowo.

**Architecture:** Zmiany wyłącznie w warstwie rozpoznawania/normalizacji kolumn
importu pracowników. Nowy czysty parser wymiaru (`import_common`), rozszerzenie
słownika synonimów (`mapping.py`), oraz krok scalająco-walidujący dwie kolumny
wymiaru w jeden kanoniczny string PRZED `AutorForm` (`parsers/wartosci.py` +
`pipeline/analyze.py`). Logika synchronizacji dat (#576, `okresy.py`) i schemat
bazy — nietknięte.

**Tech Stack:** Django, pytest (+ model_bakery, testcontainers), `Fraction`/
`Decimal` (stdlib), openpyxl (tylko w testach E2E).

**Spec:** `docs/superpowers/specs/2026-07-13-import-pracownikow-rozpoznawanie-kolumn-wykaz-design.md`

## Global Constraints

- Wszystkie polecenia Pythona przez `uv run` (NIGDY goły `python`/`pytest`).
- Max długość linii: **88 znaków** (ruff).
- **Bez migracji schematu** — żadnych zmian w `src/*/migrations/`.
- **Nie ruszać** logiki sync dat (#576): `okresy.py`,
  `models._integruj_daty_aj`, `_check_autor_jednostka_needs_update`, `roznice.py`.
- Testy w konwencji pytest: funkcje (bez klas `unittest`), `@pytest.mark.django_db`
  dla DB, `model_bakery.baker.make`.
- Weryfikacja stanu bazy (ground truth): `Wymiar_Etatu` już zawiera „dobre"
  wpisy `1`(id1), `0,5`(id2), `0,25`(id3), `0,75`(id5), `0,67`(id4) — kanoniczna
  forma polska (przecinek, minimalne cyfry) MUSI się w nie trafiać.
- Znormalizowane klucze nagłówków (zweryfikowane empirycznie na syntetycznym
  wykazie): `data_od`, `data_do`, `gł_zakład_pracy`, `wymiar_etatu`,
  `wymiar_etatu_2` (drugi identyczny nagłówek „Wymiar etatu" po
  `rename_duplicate_columns`).
- Baseline: **nie** odświeżać w tym branchu (brak migracji → i tak pusta delta);
  ewentualny refresh przy scalaniu.

---

### Task 1: Czysty parser wymiaru etatu (`parsuj_wymiar_etatu` + `kanonizuj_wymiar_etatu`)

**Files:**
- Modify: `src/import_common/normalization.py` (dodać 2 funkcje + importy `Fraction`, `Decimal`, `InvalidOperation`)
- Test: `src/import_common/tests/test_normalization.py`

**Interfaces:**
- Produces:
  - `parsuj_wymiar_etatu(s: str | None) -> Fraction | None` — pusty/None → `None`;
    „pełny/pełen/cały etat" → `Fraction(1)`; „N/M etatu" → `Fraction(N, M)`;
    dziesiętny „0,5"/„0.5"/„1" → `Fraction`; nieparsowalne → `raise ValueError`.
  - `kanonizuj_wymiar_etatu(frac: Fraction) -> str` — mianownik 1 → `"1"`;
    inaczej dziesiętny z **przecinkiem**, max 2 miejsca, bez zer końcowych
    (`Fraction(1,2)→"0,5"`, `Fraction(3,4)→"0,75"`, `Fraction(2,3)→"0,67"`).

- [ ] **Step 1: Write the failing tests**

Dopisz na końcu `src/import_common/tests/test_normalization.py`:

```python
from fractions import Fraction

from import_common.normalization import (
    kanonizuj_wymiar_etatu,
    parsuj_wymiar_etatu,
)


@pytest.mark.parametrize(
    "wejscie,oczekiwane",
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("Pełny etat", Fraction(1)),
        ("pełen etat", Fraction(1)),
        ("cały etat", Fraction(1)),
        ("1/2 etatu", Fraction(1, 2)),
        ("3/4", Fraction(3, 4)),
        ("1/4 etatu", Fraction(1, 4)),
        ("0,5", Fraction(1, 2)),
        ("0.5", Fraction(1, 2)),
        ("1", Fraction(1)),
        ("0,75", Fraction(3, 4)),
    ],
)
def test_parsuj_wymiar_etatu(wejscie, oczekiwane):
    assert parsuj_wymiar_etatu(wejscie) == oczekiwane


@pytest.mark.parametrize("smiec", ["abc", "1/0", "2/3/4", "pół"])
def test_parsuj_wymiar_etatu_smiec(smiec):
    with pytest.raises(ValueError):
        parsuj_wymiar_etatu(smiec)


@pytest.mark.parametrize(
    "frac,oczekiwane",
    [
        (Fraction(1), "1"),
        (Fraction(1, 2), "0,5"),
        (Fraction(3, 4), "0,75"),
        (Fraction(1, 4), "0,25"),
        (Fraction(2, 3), "0,67"),
    ],
)
def test_kanonizuj_wymiar_etatu(frac, oczekiwane):
    assert kanonizuj_wymiar_etatu(frac) == oczekiwane
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest src/import_common/tests/test_normalization.py -k "wymiar_etatu" -v`
Expected: FAIL — `ImportError: cannot import name 'parsuj_wymiar_etatu'`.

- [ ] **Step 3: Implement the two functions**

W `src/import_common/normalization.py` dodaj na górze (obok istniejących importów):

```python
from decimal import Decimal, InvalidOperation
from fractions import Fraction
```

Dodaj (np. obok `normalize_wymiar_etatu`):

```python
_WYMIAR_PELNY = {"pełny", "pełen", "cały", "caly", "pelny", "pelen"}


def parsuj_wymiar_etatu(s: str | None) -> Fraction | None:
    """Parsuje wymiar etatu z formy tekstowej LUB dziesiętnej do ``Fraction``.

    Pusty/None → ``None``. „Pełny/pełen/cały etat" → 1. „N/M etatu" → N/M.
    Dziesiętny „0,5"/„0.5"/„1" (polski przecinek lub kropka) → ułamek.
    Nieparsowalne → ``ValueError`` (wołający zamienia na błąd wiersza)."""
    if s is None:
        return None
    tekst = str(s).strip().lower()
    if not tekst:
        return None
    rdzen = tekst
    for sufiks in ("etatu", "etat"):
        if rdzen.endswith(sufiks):
            rdzen = rdzen[: -len(sufiks)].strip()
            break
    if rdzen in _WYMIAR_PELNY:
        return Fraction(1)
    if "/" in rdzen:
        licznik, _, mianownik = rdzen.partition("/")
        try:
            return Fraction(int(licznik.strip()), int(mianownik.strip()))
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError(f"Nieparsowalny wymiar etatu: {s!r}") from exc
    try:
        return Fraction(Decimal(rdzen.replace(",", ".")))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Nieparsowalny wymiar etatu: {s!r}") from exc


def kanonizuj_wymiar_etatu(frac: Fraction) -> str:
    """Kanoniczny zapis wymiaru: liczba całkowita bez przecinka („1"), inaczej
    ułamek dziesiętny z POLSKIM przecinkiem, max 2 miejsca, bez zer końcowych
    („0,5", „0,75", „0,67"). Trafia w istniejące „dobre" wpisy słownika."""
    if frac.denominator == 1:
        return str(frac.numerator)
    dziesietnie = (Decimal(frac.numerator) / Decimal(frac.denominator)).quantize(
        Decimal("0.01")
    )
    return format(dziesietnie.normalize(), "f").replace(".", ",")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest src/import_common/tests/test_normalization.py -k "wymiar_etatu" -v`
Expected: PASS (wszystkie parametry).

- [ ] **Step 5: Commit**

```bash
git add src/import_common/normalization.py src/import_common/tests/test_normalization.py
git commit -m "feat(import): parser wymiaru etatu tekst/ułamek -> kanoniczny Fraction"
```

---

### Task 2: Synonimy nagłówków — `Data od`/`Data do` + `Gł. zakład pracy`

**Files:**
- Modify: `src/import_pracownikow/mapping.py:113-116` (blok `_SYNONIMY`)
- Test: `src/import_pracownikow/tests/test_mapping.py`

**Interfaces:**
- Consumes: `zaproponuj_mapowanie(naglowki)`, `POLE_POMIN` (istniejące).
- Produces: rozpoznanie znormalizowanych nagłówków `data_od`→`data_zatrudnienia`,
  `data_do`→`data_końca_zatrudnienia`, `gł_zakład_pracy`/`gl_zaklad_pracy`/
  `główny_zakład_pracy`/`glowny_zaklad_pracy`→`podstawowe_miejsce_pracy`.

- [ ] **Step 1: Write the failing test**

Dopisz do `src/import_pracownikow/tests/test_mapping.py`:

```python
def test_zaproponuj_mapowanie_daty_od_do():
    prop = zaproponuj_mapowanie(["data_od", "data_do"])
    assert prop["data_od"] == "data_zatrudnienia"
    assert prop["data_do"] == "data_końca_zatrudnienia"


def test_zaproponuj_mapowanie_glowny_zaklad_pracy():
    prop = zaproponuj_mapowanie(
        ["gł_zakład_pracy", "gl_zaklad_pracy", "główny_zakład_pracy", "glowny_zaklad_pracy"]
    )
    assert prop["gł_zakład_pracy"] == "podstawowe_miejsce_pracy"
    assert prop["gl_zaklad_pracy"] == "podstawowe_miejsce_pracy"
    assert prop["główny_zakład_pracy"] == "podstawowe_miejsce_pracy"
    assert prop["glowny_zaklad_pracy"] == "podstawowe_miejsce_pracy"


def test_zaklad_pracy_nie_koliduje_z_nazwa_jednostki():
    # samo „zakład" (nazwa jednostki) NADAL → nazwa_jednostki (regres-guard).
    prop = zaproponuj_mapowanie(["zakład", "gł_zakład_pracy"])
    assert prop["zakład"] == "nazwa_jednostki"
    assert prop["gł_zakład_pracy"] == "podstawowe_miejsce_pracy"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest src/import_pracownikow/tests/test_mapping.py -k "daty_od_do or glowny_zaklad or nie_koliduje" -v`
Expected: FAIL — `data_od`/`gł_zakład_pracy` dają `__pomin__` (assert `!=`).

- [ ] **Step 3: Add the synonyms**

W `src/import_pracownikow/mapping.py`, w słowniku `_SYNONIMY`, po linii
`"data_konca_zatrudnienia": "data_końca_zatrudnienia",` dodaj:

```python
    "data_od": "data_zatrudnienia",
    "data_do": "data_końca_zatrudnienia",
    "gł_zakład_pracy": "podstawowe_miejsce_pracy",
    "gl_zaklad_pracy": "podstawowe_miejsce_pracy",
    "główny_zakład_pracy": "podstawowe_miejsce_pracy",
    "glowny_zaklad_pracy": "podstawowe_miejsce_pracy",
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest src/import_pracownikow/tests/test_mapping.py -k "daty_od_do or glowny_zaklad or nie_koliduje" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/mapping.py src/import_pracownikow/tests/test_mapping.py
git commit -m "feat(import): rozpoznaj nagłówki Data od/Data do i Gł. zakład pracy"
```

---

### Task 3: Scalanie + walidacja krzyżowa dwóch kolumn wymiaru (`scal_wymiar_etatu`)

**Files:**
- Modify: `src/import_pracownikow/parsers/wartosci.py` (nowa funkcja + importy)
- Modify: `src/import_pracownikow/pipeline/analyze.py:551` (wywołanie w `_przetworz_wiersz`)
- Test: `src/import_pracownikow/tests/test_parsers/test_wartosci.py`
- Test (wiring): `src/import_pracownikow/tests/test_pipeline/test_analyze.py`

**Interfaces:**
- Consumes: `parsuj_wymiar_etatu`, `kanonizuj_wymiar_etatu` (Task 1);
  `XLSMatchError(elem, object, reason)` (`import_common.exceptions`).
- Produces: `scal_wymiar_etatu(dane: dict) -> dict` — czyta/USUWA klucze
  `wymiar_etatu_tekst`/`wymiar_etatu_ulamek`, ustawia `dane["wymiar_etatu"]`
  na kanoniczny string; rozbieżność/śmieć → `XLSMatchError`. Gdy obu brak —
  no-op (nie ustawia `wymiar_etatu`). Mutuje i zwraca `dane`.

- [ ] **Step 1: Write the failing unit tests**

Dopisz do `src/import_pracownikow/tests/test_parsers/test_wartosci.py`:

```python
import pytest

from import_common.exceptions import XLSMatchError
from import_pracownikow.parsers.wartosci import scal_wymiar_etatu


def _dane(**over):
    d = {"__xls_loc_sheet__": 0, "__xls_loc_row__": 7}
    d.update(over)
    return d


def test_scal_wymiar_zgodne_kanonizuje():
    d = _dane(wymiar_etatu_tekst="1/2 etatu", wymiar_etatu_ulamek="0,5")
    scal_wymiar_etatu(d)
    assert d["wymiar_etatu"] == "0,5"
    assert "wymiar_etatu_tekst" not in d
    assert "wymiar_etatu_ulamek" not in d


def test_scal_wymiar_pelny_etat_zgodny_z_jeden():
    d = _dane(wymiar_etatu_tekst="Pełny etat", wymiar_etatu_ulamek="1")
    scal_wymiar_etatu(d)
    assert d["wymiar_etatu"] == "1"


def test_scal_wymiar_tylko_ulamek():
    d = _dane(wymiar_etatu_ulamek="0,75")
    scal_wymiar_etatu(d)
    assert d["wymiar_etatu"] == "0,75"


def test_scal_wymiar_tylko_tekst():
    d = _dane(wymiar_etatu_tekst="3/4 etatu")
    scal_wymiar_etatu(d)
    assert d["wymiar_etatu"] == "0,75"


def test_scal_wymiar_brak_obu_noop():
    d = _dane(nazwisko="Kowalski")
    scal_wymiar_etatu(d)
    assert "wymiar_etatu" not in d


def test_scal_wymiar_tolerancja_zaokraglenia():
    # 2/3 (0.6667) vs 0,67 — zgodne po zaokrągleniu do 2 miejsc.
    d = _dane(wymiar_etatu_tekst="2/3 etatu", wymiar_etatu_ulamek="0,67")
    scal_wymiar_etatu(d)
    assert d["wymiar_etatu"] == "0,67"


def test_scal_wymiar_rozbieznosc_rzuca():
    d = _dane(wymiar_etatu_tekst="1/2 etatu", wymiar_etatu_ulamek="1")
    with pytest.raises(XLSMatchError):
        scal_wymiar_etatu(d)


def test_scal_wymiar_smiec_rzuca():
    d = _dane(wymiar_etatu_ulamek="abc")
    with pytest.raises(XLSMatchError):
        scal_wymiar_etatu(d)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest src/import_pracownikow/tests/test_parsers/test_wartosci.py -k scal_wymiar -v`
Expected: FAIL — `ImportError: cannot import name 'scal_wymiar_etatu'`.

- [ ] **Step 3: Implement `scal_wymiar_etatu`**

W `src/import_pracownikow/parsers/wartosci.py` dodaj importy (na górze, po
istniejących):

```python
from import_common.exceptions import XLSMatchError
from import_common.normalization import (
    kanonizuj_wymiar_etatu,
    parsuj_wymiar_etatu,
)
```

Dodaj funkcję (np. po `normalizuj_wartosci_wiersza`):

```python
def scal_wymiar_etatu(dane: dict) -> dict:
    """Scala dwie kolumny wymiaru etatu („(tekst)" + „(ułamek)") w jeden
    kanoniczny string pod kluczem ``wymiar_etatu`` (konsumowany dalej przez
    ``AutorForm`` + ``matchuj_wymiar_etatu``). Obie niosą tę SAMĄ informację;
    rozbieżność (po zaokrągleniu do 2 miejsc) albo nieparsowalna forma →
    ``XLSMatchError`` (błąd wiersza, analiza fail-fast, komunikat wskazuje
    wiersz i obie wartości). Kolumna ułamkowa jest autorytatywna dla zapisu;
    tekst służy do walidacji. Mutuje i zwraca ``dane``."""
    tekst_raw = dane.pop("wymiar_etatu_tekst", None)
    ulamek_raw = dane.pop("wymiar_etatu_ulamek", None)
    try:
        tekst = parsuj_wymiar_etatu(tekst_raw)
        ulamek = parsuj_wymiar_etatu(ulamek_raw)
    except ValueError as exc:
        raise XLSMatchError(dane, "wymiar_etatu", str(exc)) from exc
    if (
        tekst is not None
        and ulamek is not None
        and round(float(tekst), 2) != round(float(ulamek), 2)
    ):
        raise XLSMatchError(
            dane,
            "wymiar_etatu",
            f"Rozbieżny wymiar etatu: tekst {tekst_raw!r} (={float(tekst)}) "
            f"≠ ułamek {ulamek_raw!r} (={float(ulamek)})",
        )
    wybrany = ulamek if ulamek is not None else tekst
    if wybrany is not None:
        dane["wymiar_etatu"] = kanonizuj_wymiar_etatu(wybrany)
    return dane
```

- [ ] **Step 4: Run the unit tests to verify they pass**

Run: `uv run pytest src/import_pracownikow/tests/test_parsers/test_wartosci.py -k scal_wymiar -v`
Expected: PASS (wszystkie 8).

- [ ] **Step 5: Wire into `_przetworz_wiersz`**

W `src/import_pracownikow/pipeline/analyze.py`, w `_przetworz_wiersz`, tuż po
linii `dane_form = normalizuj_wartosci_wiersza(elem)` (obecnie 551) dodaj:

```python
    # Dwie kolumny „Wymiar etatu" (tekst + ułamek) → jeden kanoniczny string
    # pod „wymiar_etatu" PRZED AutorForm; rozbieżność → XLSMatchError (§4).
    scal_wymiar_etatu(dane_form)
```

Zaktualizuj import w `analyze.py` (blok importów z `parsers.wartosci`) — dodaj
`scal_wymiar_etatu`. Znajdź istniejący import i dołóż nazwę, np.:

```python
from import_pracownikow.parsers.wartosci import (
    normalizuj_wartosci_wiersza,
    scal_wymiar_etatu,
)
```

(Jeśli `normalizuj_wartosci_wiersza` jest importowana inną ścieżką/aliasem —
dopisz `scal_wymiar_etatu` obok niej; sprawdź górę pliku `analyze.py`.)

- [ ] **Step 6: Write the failing wiring test**

Dopisz do `src/import_pracownikow/tests/test_pipeline/test_analyze.py`:

```python
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
```

Dodaj na górze pliku import: `from import_common.exceptions import XLSMatchError`.

> Uwaga: sprawdź, czy `row.dane_znormalizowane` przechowuje `wymiar_etatu` jako
> string — jeśli klucz w znormalizowanych danych nazywa się inaczej, użyj tego,
> co faktycznie zapisuje `_dane_znormalizowane_z_parserem`. Jeśli wygodniej,
> asertuj przez `row.wymiar_etatu` (FK) po dodaniu wpisu `Wymiar_Etatu` bakerem
> „0,5" — wtedy `assert row.wymiar_etatu.nazwa == "0,5"`.

- [ ] **Step 7: Run the wiring tests**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_analyze.py -k "scala_podwojny or rozbiezny_wymiar" -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/import_pracownikow/parsers/wartosci.py \
        src/import_pracownikow/pipeline/analyze.py \
        src/import_pracownikow/tests/test_parsers/test_wartosci.py \
        src/import_pracownikow/tests/test_pipeline/test_analyze.py
git commit -m "feat(import): scalanie+walidacja krzyżowa podwójnego wymiaru etatu"
```

---

### Task 4: Rozdzielenie wymiaru na dwa pola docelowe w mapowaniu

**Files:**
- Modify: `src/import_pracownikow/mapping.py:27` (`POLA_DOCELOWE`) i `:110-112` (`_SYNONIMY`)
- Test: `src/import_pracownikow/tests/test_mapping.py`

**Interfaces:**
- Consumes: `POLA_DOCELOWE`, `zaproponuj_mapowanie`, `remapuj_wiersz`.
- Produces: dwa nagłówki „Wymiar etatu" (po dedup → `wymiar_etatu` /
  `wymiar_etatu_2`) mapują się na `wymiar_etatu_tekst` / `wymiar_etatu_ulamek`
  (konsumowane przez `scal_wymiar_etatu` z Task 3).

- [ ] **Step 1: Write the failing test**

Dopisz do `src/import_pracownikow/tests/test_mapping.py`:

```python
def test_pola_docelowe_maja_dwa_wymiary():
    klucze = {k for k, _ in POLA_DOCELOWE}
    assert "wymiar_etatu_tekst" in klucze
    assert "wymiar_etatu_ulamek" in klucze


def test_podwojny_wymiar_mapuje_sie_na_dwa_pola():
    # dwie identyczne kolumny „Wymiar etatu" po rename_duplicate_columns →
    # wymiar_etatu / wymiar_etatu_2 (znormalizowane).
    prop = zaproponuj_mapowanie(["wymiar_etatu", "wymiar_etatu_2"])
    assert prop["wymiar_etatu"] == "wymiar_etatu_tekst"
    assert prop["wymiar_etatu_2"] == "wymiar_etatu_ulamek"


def test_pojedynczy_wymiar_mapuje_na_tekst():
    prop = zaproponuj_mapowanie(["wymiar_etatu"])
    assert prop["wymiar_etatu"] == "wymiar_etatu_tekst"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest src/import_pracownikow/tests/test_mapping.py -k "dwa_wymiary or podwojny_wymiar or pojedynczy_wymiar" -v`
Expected: FAIL — brak `wymiar_etatu_tekst` w `POLA_DOCELOWE`; `wymiar_etatu`
mapuje się na `wymiar_etatu` (stare).

- [ ] **Step 3: Split target fields + synonyms**

W `src/import_pracownikow/mapping.py`, w `POLA_DOCELOWE`, ZAMIEŃ linię
`("wymiar_etatu", "Wymiar etatu"),` na:

```python
    ("wymiar_etatu_tekst", "Wymiar etatu (tekst)"),
    ("wymiar_etatu_ulamek", "Wymiar etatu (ułamek)"),
```

W `_SYNONIMY`, ZAMIEŃ trzy linie
```python
    "wymiar_etatu": "wymiar_etatu",
    "etat": "wymiar_etatu",
    "wymiar": "wymiar_etatu",
```
na:
```python
    "wymiar_etatu": "wymiar_etatu_tekst",
    "wymiar_etatu_2": "wymiar_etatu_ulamek",
    "etat": "wymiar_etatu_tekst",
    "wymiar": "wymiar_etatu_tekst",
```

- [ ] **Step 4: Run the mapping tests to verify they pass**

Run: `uv run pytest src/import_pracownikow/tests/test_mapping.py -k "dwa_wymiary or podwojny_wymiar or pojedynczy_wymiar" -v`
Expected: PASS.

- [ ] **Step 5: Run the whole mapping + analyze suite (regres wiring z Task 3)**

Run: `uv run pytest src/import_pracownikow/tests/test_mapping.py src/import_pracownikow/tests/test_pipeline/test_analyze.py -q`
Expected: PASS (scalanie z Task 3 aktywuje się teraz end-to-end przy remapowaniu).

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/mapping.py src/import_pracownikow/tests/test_mapping.py
git commit -m "feat(import): rozdziel Wymiar etatu na pola (tekst)+(ułamek)"
```

---

### Task 5: E2E na syntetycznym wykazie + newsfragment

**Files:**
- Test: `src/import_pracownikow/tests/test_pipeline/test_analyze_wykaz.py` (nowy)
- Create: `src/bpp/newsfragments/import-kolumny-wykaz.feature.rst`

**Interfaces:**
- Consumes: cały łańcuch (`otworz_zrodlo` → `naglowki_i_probka` →
  `zaproponuj_mapowanie` → `analizuj`). Bez mocków źródła — realny XLSX.

- [ ] **Step 1: Write the failing E2E test (real synthetic xlsx)**

Utwórz `src/import_pracownikow/tests/test_pipeline/test_analyze_wykaz.py`:

```python
import openpyxl
import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor_Jednostka
from import_pracownikow.mapping import zaproponuj_mapowanie
from import_pracownikow.models import ImportPracownikow
from import_pracownikow.pipeline.analyze import analizuj

# Nagłówki jak w prawdziwym „wykaz 2026.xlsx" (dane w teście SYNTETYCZNE).
_NAGLOWKI = [
    "Lp.", "NUMER", None, "Nazwisko", "Imię ", "Tytuł/ Stopień", "Stanowisko",
    "Grupa pracownicza", "Nazwa jednostki", "Wydział", "Data od",
    "Gł. zakład pracy", "Wymiar etatu", "Wymiar etatu", "Data do",
]


def _zapisz_wykaz(path, autor, jednostka):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "30.06.2026"
    ws.append(_NAGLOWKI)
    ws.append([
        1, 1000, None, autor.nazwisko, autor.imiona, "dr", "Adiunkt",
        "Badawcza", jednostka.nazwa, "Wydział Testowy", "2020-01-01",
        "T", "1/2 etatu", "0,5", "2025-12-31",
    ])
    wb.save(path)


@pytest.mark.django_db
def test_wykaz_rozpoznaje_daty_glowny_zaklad_i_wymiar(
    dwa_autory_z_jednostka, tmp_path
):
    autor, jednostka = dwa_autory_z_jednostka
    baker.make("bpp.Wymiar_Etatu", nazwa="0,5")  # istniejący „dobry" wpis
    plik = tmp_path / "wykaz.xlsx"
    _zapisz_wykaz(plik, autor, jednostka)

    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls.name = "protected/import_pracownikow/wykaz.xlsx"
    # auto-mapowanie z nagłówków pliku (jak ekran mapowania):
    naglowki, _probka = imp_naglowki(imp, plik)
    imp.mapowanie_kolumn = zaproponuj_mapowanie(naglowki)
    imp.save()

    # Wskaż analizie właściwy plik (omijamy storage — czytamy z tmp_path):
    with _plik_xls(imp, plik):
        analizuj(imp, MockProgress(imp))

    row = imp.importpracownikowrow_set.get()
    dn = row.dane_znormalizowane
    assert dn.get("data_zatrudnienia")            # „Data od" rozpoznane
    assert dn.get("wymiar_etatu") == "0,5"         # podwójny wymiar → kanoniczny
    # „Gł. zakład pracy" = T → podstawowe miejsce pracy = prawda:
    assert dn.get("podstawowe_miejsce_pracy") is True
```

Pomocnicze (dopisz w tym samym pliku, dopasowując do realnego API dostępu do
`plik_xls.path`; jeśli w projekcie jest już fixture ładujący plik do storage
importu — użyj jej zamiast poniższych):

```python
import contextlib


def imp_naglowki(imp, plik):
    from import_common.sources import otworz_zrodlo
    from import_pracownikow.mapping import MIN_POINTS, TRY_NAMES

    zrodlo = otworz_zrodlo(str(plik), try_names=TRY_NAMES, min_points=MIN_POINTS)
    rows = list(zrodlo.data())
    naglowki = [
        k for k in rows[0]
        if k not in ("__xls_loc_sheet__", "__xls_loc_row__")
    ]
    return naglowki, rows[: 10]


@contextlib.contextmanager
def _plik_xls(imp, plik):
    # analizuj czyta imp.plik_xls.path — podmieniamy na ścieżkę tmp_path.
    from unittest.mock import patch, PropertyMock

    with patch.object(
        type(imp).plik_xls.field, "storage"
    ):  # noqa: SIM117
        with patch(
            "django.db.models.fields.files.FieldFile.path",
            new_callable=PropertyMock,
            return_value=str(plik),
        ):
            yield
```

> **Uproszczenie, jeśli powyższe podmienianie `path` jest kruche:** zamiast
> realnego `analizuj`, przetestuj łańcuch mapowania na realnym XLSX bez DB:
> otwórz `otworz_zrodlo(str(plik))`, weź `rows[0]`, policz
> `zaproponuj_mapowanie(naglowki)` i `remapuj_wiersz(rows[0], mapowanie)`, potem
> `scal_wymiar_etatu(...)` i asertuj `data_zatrudnienia`/`data_końca_zatrudnienia`
> obecne, `podstawowe_miejsce_pracy == "T"`, `wymiar_etatu == "0,5"`. To pokrywa
> całą warstwę rozpoznawania kolumn bez fixture'ów storage. Wybierz wariant,
> który pasuje do istniejących testów E2E modułu (sprawdź, jak `test_analyze.py`
> ładuje realne pliki — plik `testdata_brak_naglowka.xlsx` sugeruje istniejący
> wzorzec).

- [ ] **Step 2: Run the E2E test to verify it fails**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_analyze_wykaz.py -v`
Expected: FAIL (albo na braku rozpoznania — jeśli uruchomione przed Task 2/4 —
albo przechodzi, jeśli po; przy TDD w tej kolejności ma PRZEJŚĆ, bo Task 2–4 już
zaimplementowane. Jeśli przechodzi od razu, potraktuj jako test regresyjny
potwierdzający integrację).

- [ ] **Step 3: Adjust until green**

Dostosuj asercje/dostęp do pliku do realnego API modułu (patrz notka wyżej).
Kryterium: test zielony i faktycznie przechodzi przez rozpoznanie nagłówków +
scalanie wymiaru.

- [ ] **Step 4: Add newsfragment**

Utwórz `src/bpp/newsfragments/import-kolumny-wykaz.feature.rst`:

```rst
Import pracowników rozpoznaje teraz kolumny „Data od"/„Data do" (daty
zatrudnienia), „Gł. zakład pracy" (podstawowe miejsce pracy) oraz podwójną
kolumnę „Wymiar etatu" (tekst + ułamek), sprowadzając wymiar do jednej
kanonicznej postaci i odrzucając wiersz, gdy obie wersje wymiaru się różnią.
```

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/tests/test_pipeline/test_analyze_wykaz.py \
        src/bpp/newsfragments/import-kolumny-wykaz.feature.rst
git commit -m "test(import): E2E rozpoznania kolumn wykazu 2026 + newsfragment"
```

---

### Task 6: Regresja — moduł + pełna suita

**Files:** — (brak zmian kodu; weryfikacja)

- [ ] **Step 1: Moduł importu — zielony**

Run: `uv run pytest src/import_pracownikow/ src/import_common/ -q 2>&1 | tee /tmp/wykaz_modul.log; echo "EXIT=${PIPESTATUS[0]}"`
Expected: `EXIT=0`, 0 failed. (Uwaga na pamięć: nie uruchamiaj dwa razy — czytaj
z `/tmp/wykaz_modul.log`.)

- [ ] **Step 2: Pełna suita (regresja, ~10 min)**

Run: `make tests-without-playwright 2>&1 | tee /tmp/wykaz_full.log; echo "EXIT=${PIPESTATUS[0]}" >> /tmp/wykaz_full.log`
Expected: `EXIT=0`, brak nowych failów względem `dev`.
(Znane pre-existing RED na dev: 17 testów `api_v1/test_autor` — niezwiązane,
patrz pamięć projektu. Zweryfikuj, że NIE przybyło nowych.)

- [ ] **Step 3: Ręczna weryfikacja na prawdziwym pliku (opcjonalnie, user)**

Poproś usera o wgranie `wykaz 2026.xlsx` przez UI importu i potwierdzenie, że
ekran mapowania auto-rozpoznaje `Data od`/`Data do`, `Gł. zakład pracy` oraz oba
`Wymiar etatu`, a podgląd pokazuje kanoniczny wymiar. (RODO: agent nie czyta
pełnego pliku.)

---

## Self-Review

**Spec coverage:**
- §2 A (Data od/do synonimy) → Task 2. ✓
- §2.2 (daty ISO) → już obsługiwane przez `ExcelDateField` (istniejący test
  `test_normalize_date_pl` potwierdza „2016-10-01" zostawiane formularzowi);
  E2E (Task 5) potwierdza end-to-end. ✓ (bez zmian kodu — świadomie).
- §3 B (Gł. zakład pracy synonimy + T/N) → Task 2 (synonimy) + `normalize_boolean`
  bez zmian (T/N już działa, potwierdzone). ✓
- §4 C (parser + kanonizacja + walidacja krzyżowa + scalenie) → Task 1 (parser/
  kanonizacja), Task 3 (scal + wiring), Task 4 (rozdział pól). ✓
- §5 (błąd wiersza) → Task 3 `XLSMatchError` (fail-fast, wskazuje wiersz+wartości). ✓
- §6 (testy) → Task 1–5. ✓
- §7 (brak migracji, baseline przy scalaniu) → Global Constraints + Task 6. ✓

**Placeholder scan:** brak TBD/TODO; każdy krok ma realny kod i polecenie.
Jedyne „dopasuj do realnego API" dotyczy dostępu do pliku w E2E — z jawnym
wariantem awaryjnym (test warstwy mapowania bez storage). ✓

**Type consistency:** `parsuj_wymiar_etatu -> Fraction|None`,
`kanonizuj_wymiar_etatu(Fraction)->str`, `scal_wymiar_etatu(dict)->dict` —
używane spójnie w Task 3/4/5. Klucze `wymiar_etatu_tekst`/`wymiar_etatu_ulamek`
identyczne w mapping (Task 4) i scal (Task 3). `XLSMatchError(elem, object,
reason)` zgodne z sygnaturą z `exceptions.py`. ✓

**Uwaga do kolejności:** Task 3 (scal + wiring) PRZED Task 4 (rozdział pól) jest
celowe — po Task 3 pipeline działa jak dawniej (brak kluczy tekst/ułamek →
`scal` no-op, stary klucz `wymiar_etatu` nietknięty), a Task 4 aktywuje scalanie
end-to-end. Każdy commit zostawia działający moduł.
