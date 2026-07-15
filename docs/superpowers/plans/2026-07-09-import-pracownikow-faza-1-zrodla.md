# Import pracowników — Faza 1: warstwa źródeł CSV + XLSX

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dodać obsługę plików **CSV** obok XLSX w imporcie pracowników, przez
wspólną abstrakcję `TabularSource`, bez zmiany zachowania dla istniejących
plików XLSX.

**Architecture:** Wynosimy rdzeń wykrywania nagłówka (`find_similar_row`) do
funkcji operującej na gołych listach wartości (`find_similar_row_in_rows`), tak
by ten sam kod obsłużył komórki openpyxl (XLSX) i stringi (CSV). Nad tym stoi
protokół `TabularSource` z dwiema implementacjami — `XLSXSource` (opakowanie
istniejącego `XLSImportFile`, zero zmian logiki parsowania) i `CSVSource` (nowa:
detekcja formatu po magic-bytes, encodingu, delimitera). Fabryka `otworz_zrodlo`
wykrywa format i zwraca właściwe źródło. `analizuj()` (Faza 0) przełącza się z
`XLSImportFile` na fabrykę i normalizuje wartości (daty `DD.MM.YYYY`) przed
walidacją formularzem.

**Tech Stack:** Python 3.10+, Django, openpyxl (XLSX, istniejące), stdlib `csv`
(CSV, bez nowej zależności), pytest + model_bakery.

## Global Constraints

- **Max długość linii: 88 znaków** (ruff).
- **Zawsze `uv run`** dla poleceń Pythona (`uv run pytest ...`).
- **Faza 1 NIE ma migracji schematu** (§12 specyfikacji) — żadnych plików w
  `src/*/migrations/`. Nie tykać istniejących migracji.
- **Backward compatibility (krytyczne):** istniejący callerzy refaktorowanych
  funkcji MUSZĄ zostać zielone bez zmian w ich kodzie:
  `import_common.util.znajdz_naglowek` (używany przez
  `import_dyscyplin/models.py:230`), `XLSImportFile` (używany przez
  `import_common/models.py`, `import_pracownikow`), oraz testy
  `src/import_common/tests/test_util.py`.
- **Bez `except: pass`** — każdy wyjątek loguje, re-raise'uje albo zwraca sens.
  Wąski typ + komentarz „dlaczego" dozwolony.
- **Komentarze szablonów Django `{# #}` jedno-liniowe** (nie dotyczy tej fazy —
  brak zmian w szablonach).
- **pytest, nie unittest.TestCase**; funkcje-testy bez klas; `@pytest.mark.django_db`
  tylko gdy potrzebna baza; `model_bakery.baker.make` do obiektów.
- **PESEL zakazany**: `DEFAULT_BANNED_NAMES` (`pesel`, `pesel_md5`, `peselmd5`)
  odrzucane w KAŻDYM źródle (także CSV).
- **Kontrakt kluczy lokalizacyjnych:** każdy wiersz z każdego źródła MUSI
  emitować `__xls_loc_sheet__` i `__xls_loc_row__` (CSV: `sheet=0`, `row=n`) —
  `get_details_set()` sortuje po nich.

---

## File Structure

**Tworzone:**
- `src/import_common/sources.py` — `TabularSource` (Protocol), `XLSXSource`,
  `CSVSource`, `wykryj_format`, `otworz_zrodlo`, helpery encodingu/delimitera.
- `src/import_pracownikow/parsers/__init__.py` — pusty (nowy pakiet).
- `src/import_pracownikow/parsers/wartosci.py` — normalizacja wartości
  (daty `DD.MM.YYYY`) nad źródłem.
- `src/import_common/tests/test_sources.py` — testy `wykryj_format`, `XLSXSource`,
  `CSVSource` (encoding/delimiter/nagłówek/banned/loc-keys/puste/brak nagłówka).
- `src/import_pracownikow/tests/test_parsers/__init__.py`
- `src/import_pracownikow/tests/test_parsers/test_wartosci.py` — testy tabelaryczne
  normalizacji dat.
- `src/import_pracownikow/tests/test_pipeline/test_analyze_csv.py` — test
  end-to-end CSV przez pełną `analizuj()`.
- `src/bpp/newsfragments/import-pracownikow-csv-zrodla.feature.rst` — newsfragment.

**Modyfikowane:**
- `src/import_common/util.py` — refaktor `normalize_cell_header` (przyjmuje
  surową wartość) + nowe `find_similar_row_in_rows`; `find_similar_row` staje się
  cienkim wrapperem (bez zmiany sygnatury/zachowania dla callerów).
- `src/import_pracownikow/pipeline/analyze.py` — `otworz_zrodlo` zamiast
  `XLSImportFile` + normalizacja wartości wiersza.
- `src/import_pracownikow/tests/test_pipeline/test_analyze.py` — patch celu
  `otworz_zrodlo` zamiast `XLSImportFile` (3 istniejące testy).

**Poza zakresem (świadomie odłożone — nie flagować jako braki):**
- Mapowanie kolumn / profile / ekran korekty → **Faza 2**.
- Walidacja spójności nagłówków między arkuszami XLSX → **Faza 2** (ma sens
  dopiero z mapowaniem „jedno na cały import"; Faza 1 zachowuje istniejące
  per-arkuszowe zachowanie `XLSImportFile`).
- Jawny błąd „nie znaleziono nagłówka" dla **XLSX** — zostaje istniejące
  zachowanie `XLSImportFile` (ciche 0 wierszy → `ValueError` w `analizuj`), bo
  zmiana dotknęłaby współdzielonego `XLSImportFile`. **CSVSource** rzuca
  `HeaderNotFoundException` jawnie (nowy kod, bez ryzyka regresji).
- Parser sklejonej komórki, wskaźnik pewności → **Faza 3**.
- **Semantyczna** normalizacja wartości niebędących datami — `wartosci.py` (Task 4)
  robi tylko daty (`DD.MM.YYYY`), bo to jedyna luka, której istniejące normalizatory
  nie zamykają. Booleany (`TAK`/`NIE`/`t`/`p`/`f`/`n`) obsługuje już
  `normalize_nullboleanfield` (używany w `analyze._przetworz_wiersz`); mapowanie
  numerycznego wymiaru etatu (`"1,0"`/`"0.5"` → `Wymiar_Etatu`) to **matchowanie
  słownikowe**, które w Fazie 0/1 idzie przez `matchuj_wymiar_etatu` +
  `diff_do_utworzenia`, a jego rozszerzenie o warianty numeryczne należy do
  **Fazy 2/3** (normalizacja pod mapowanie). Robustność **detekcji delimitera**
  wobec przecinka dziesiętnego `0,5` JEST w Fazie 1 (test
  `test_csvsource_srednik_wygrywa_z_przecinkiem_dziesietnym`, §13).

---

### Task 1: Refaktor rdzenia fuzzy-header na wartości (backward compatible)

Wyciągamy rdzeń wykrywania nagłówka tak, by działał na gołych listach wartości
(str/None), nie tylko na komórkach openpyxl. `normalize_cell_header` zaczyna
przyjmować **surową wartość**; `find_similar_row` zostaje jako wrapper.

**Files:**
- Modify: `src/import_common/util.py:46-73`
- Test: `src/import_common/tests/test_util.py` (dodaj testy; istniejące muszą
  zostać zielone)

**Interfaces:**
- Produces:
  - `normalize_cell_header(value: str | None) -> str` — normalizuje surową
    wartość (str/None/liczba/datetime), NIE openpyxl `Cell`.
  - `find_similar_row_in_rows(rows, try_names=None, min_points=None,
    max_row_length=128) -> tuple[list[str], int] | None` — `rows` to iterowalne
    list wartości; zwraca `(znormalizowane_nazwy, n_1based)` albo `None`.
  - `find_similar_row(sheet, try_names=None, min_points=None,
    max_row_length=128)` — bez zmiany sygnatury; deleguje do
    `find_similar_row_in_rows` po wyciągnięciu `cell.value`.

- [ ] **Step 1: Napisz failing testy**

Dopisz na końcu `src/import_common/tests/test_util.py`:

```python
from import_common.util import find_similar_row_in_rows, normalize_cell_header


def test_normalize_cell_header_surowa_wartosc():
    # przyjmuje goły string (nie openpyxl Cell)
    assert normalize_cell_header("Nazwa jednostki") == "nazwa_jednostki"
    # wtrącony \n — bierze tylko PIERWSZĄ linię (wzorzec BPP), reszta odpada
    assert normalize_cell_header("Podstawowe miejsce pracy \nTAK/NIE") == (
        "podstawowe_miejsce_pracy"
    )
    # None → "none" (spójne z dawnym str(elem.value))
    assert normalize_cell_header(None) == "none"


def test_find_similar_row_in_rows_znajduje_naglowek():
    rows = [
        ["Objaśnienie", "", ""],
        ["Nazwisko", "Imię", "Jednostka", "Orcid", "Stanowisko"],
        ["Kowalski", "Jan", "Katedra", "", "Asystent"],
    ]
    res = find_similar_row_in_rows(rows, min_points=3)
    assert res is not None
    kolumny, n = res
    assert n == 2  # 1-based numer wiersza nagłówka
    assert "nazwisko" in kolumny and "jednostka" in kolumny


def test_find_similar_row_in_rows_brak_naglowka():
    rows = [["a", "b"], ["c", "d"]]
    assert find_similar_row_in_rows(rows, min_points=3) is None
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_common/tests/test_util.py -v`
Expected: FAIL na `ImportError: cannot import name 'find_similar_row_in_rows'`.

- [ ] **Step 3: Refaktor `util.py`**

Zastąp w `src/import_common/util.py` obecne `normalize_cell_header` (linie 46-54)
i `find_similar_row` (linie 57-73) tym:

```python
def normalize_cell_header(value):
    """Normalizuje SUROWĄ wartość komórki nagłówka (str/None/liczba/datetime),
    NIE openpyxl ``Cell`` — dzięki temu ten sam kod obsługuje XLSX (openpyxl)
    i CSV (stringi)."""
    s = str(value).lower().split("\n")[0]

    s = s.replace(".", " ")
    while s.find("  ") >= 0:
        s = s.replace("  ", " ")
    s = s.strip()

    return s.replace(" ", "_").replace("/", "_").replace("\\", "_").replace("-", "_")


def find_similar_row_in_rows(
    rows, try_names=None, min_points=None, max_row_length=128
):
    """Rdzeń fuzzy-detekcji nagłówka nad gołymi listami wartości.

    :param rows: iterowalne wierszy; każdy wiersz to lista wartości (str/None/…)
    :return: ``(znormalizowane_nazwy, n_1based)`` pierwszego wiersza z
        ``>= min_points`` trafień, albo ``None``.
    """
    if try_names is None:
        try_names = DEFAULT_COL_NAMES

    if min_points is None:
        min_points = DEFAULT_MIN_POINTS

    for n, row in enumerate(rows, start=1):
        r = [normalize_cell_header(v) for v in row[:max_row_length]]
        points = 0
        for elem in try_names:
            if elem in r:
                points += 1
        if points >= min_points:
            return r, n


def find_similar_row(sheet, try_names=None, min_points=None, max_row_length=128):
    """Wrapper zachowujący dotychczasową sygnaturę (openpyxl ``Worksheet``):
    wyciąga ``cell.value`` z każdej komórki i deleguje do
    ``find_similar_row_in_rows``. Istniejący callerzy (``znajdz_naglowek``,
    ``XLSImportFile``) nie wymagają zmian."""
    rows = ([cell.value for cell in row] for row in sheet.rows)
    return find_similar_row_in_rows(rows, try_names, min_points, max_row_length)
```

**Usuń martwy import (F401 → ruff/pre-commit).** Wrapper `find_similar_row`
traci adnotację `sheet: Worksheet` (nowa sygnatura jest bez adnotacji), więc
`from openpyxl.worksheet.worksheet import Worksheet` (`util.py:26`, blok
`TYPE_CHECKING`) staje się nieużywany — `ruff` zgłasza F401 także pod
`TYPE_CHECKING` (`F` jest w `select`). **Usuń tę linię importu** i uaktualnij
komentarz w liniach 20-22 (usuń wzmiankę o „``Worksheet`` /"), zostawiając
`import openpyxl` (nadal używany przez adnotację `xl_workbook`). Po zmianie
`grep -n Worksheet src/import_common/util.py` musi być pusty.

- [ ] **Step 4: Uruchom — zielone (nowe + backward-compat)**

Run: `uv run pytest src/import_common/tests/test_util.py -v`
Expected: PASS wszystkie (nowe 3 + istniejące `test_znajdz_naglowek_*`).

- [ ] **Step 5: Regresja callerów + lint (F401 martwego importu)**

Run: `uv run pytest src/import_common/tests/ -q`
Expected: PASS (żadnej regresji w `test_core`, `test_util`, itd.).

Run: `ruff check src/import_common/util.py`
Expected: brak błędów (w szczególności BRAK F401 na `Worksheet` — potwierdza,
że import usunięto).

- [ ] **Step 6: Commit**

```bash
git add src/import_common/util.py src/import_common/tests/test_util.py
git commit -m "refactor(import_common): wyciągnij find_similar_row_in_rows nad wartościami (Faza 1 T1)"
```

---

### Task 2: `TabularSource` protocol + `XLSXSource` + `wykryj_format`

Protokół źródła (minimalny — `count()` + `data()`, dokładnie to, co konsumuje
`analizuj()`), opakowanie XLSX i detekcja formatu po magic-bytes.

**Files:**
- Create: `src/import_common/sources.py`
- Test: `src/import_common/tests/test_sources.py`

**Interfaces:**
- Consumes: `import_common.util.XLSImportFile`, `DEFAULT_BANNED_NAMES`.
- Produces:
  - `class TabularSource(Protocol)` z `count() -> int` i
    `data() -> Iterator[dict]`.
  - `class XLSXSource` — `__init__(path, *, try_names=None, min_points=None,
    banned_names=None)`, deleguje do `XLSImportFile`.
  - `wykryj_format(path) -> str` — `"xlsx"` (magic-bytes `PK`) albo `"csv"`.

- [ ] **Step 1: Napisz failing testy**

Utwórz `src/import_common/tests/test_sources.py`:

```python
from import_common.sources import XLSXSource, wykryj_format


def test_wykryj_format_xlsx_po_magic_bytes(test1_xlsx):
    # XLSX = archiwum ZIP, zaczyna się od b"PK"
    assert wykryj_format(test1_xlsx) == "xlsx"


def test_wykryj_format_csv_gdy_nie_zip(tmp_path):
    p = tmp_path / "dane.csv"
    p.write_text("Nazwisko;Imię\nKowalski;Jan\n", encoding="utf-8")
    assert wykryj_format(str(p)) == "csv"


def test_xlsxsource_deleguje_do_xlsimportfile(default_xlsx):
    src = XLSXSource(default_xlsx)
    # count() i data() zwracają to samo, co XLSImportFile
    assert src.count() >= 0
    wiersze = list(src.data())
    assert len(wiersze) == src.count()
    if wiersze:
        # kontrakt kluczy lokalizacyjnych
        assert "__xls_loc_sheet__" in wiersze[0]
        assert "__xls_loc_row__" in wiersze[0]
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_common/tests/test_sources.py -v`
Expected: FAIL na `ModuleNotFoundError: No module named 'import_common.sources'`.

- [ ] **Step 3: Implementuj `sources.py` (część 1)**

Utwórz `src/import_common/sources.py`:

```python
"""Warstwa źródeł tabelarycznych dla importów (XLSX + CSV).

``TabularSource`` to wspólny protokół (``count()`` + ``data()``), którego
oczekuje pipeline importu. ``XLSXSource`` opakowuje istniejący
``XLSImportFile`` (openpyxl) bez zmian logiki parsowania. ``CSVSource``
(Task 3) dokłada obsługę CSV. ``otworz_zrodlo`` (Task 5) wykrywa format po
magic-bytes i zwraca właściwą implementację.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from .util import XLSImportFile


class TabularSource(Protocol):
    """Minimalny kontrakt konsumowany przez pipeline importu.

    ``data()`` MUSI emitować w każdym słowniku klucze lokalizacyjne
    ``__xls_loc_sheet__`` i ``__xls_loc_row__`` (kontrakt sortowania
    ``get_details_set``)."""

    def count(self) -> int: ...

    def data(self) -> Iterator[dict]: ...


class XLSXSource:
    """Adapter na istniejący ``XLSImportFile`` (openpyxl)."""

    def __init__(
        self, path, *, try_names=None, min_points=None, banned_names=None
    ):
        self._xif = XLSImportFile(
            path,
            try_names=try_names,
            min_points=min_points,
            banned_names=banned_names,
        )

    def count(self) -> int:
        return self._xif.count()

    def data(self) -> Iterator[dict]:
        return self._xif.data()


def wykryj_format(path) -> str:
    """Wykrywa format po MAGIC-BYTES, nie po rozszerzeniu (ludzie nazywają
    ``.xls`` plik CSV i odwrotnie). XLSX = archiwum ZIP → zaczyna się od PEŁNEJ
    sygnatury local-file-header ``b"PK\\x03\\x04"`` (4 bajty, nie samo ``PK`` —
    inaczej CSV z pierwszą kolumną „PKD"/„PKB"/„PK" byłby wzięty za XLSX i
    wywalił openpyxl). Reszta = CSV (stary binarny ``.xls`` BIFF nie jest
    wspierany — openpyxl i tak go nie czyta)."""
    with open(path, "rb") as f:
        sygnatura = f.read(4)
    if sygnatura == b"PK\x03\x04":
        return "xlsx"
    return "csv"
```

- [ ] **Step 4: Uruchom — zielone**

Run: `uv run pytest src/import_common/tests/test_sources.py -v`
Expected: PASS (3 testy).

- [ ] **Step 5: Commit**

```bash
git add src/import_common/sources.py src/import_common/tests/test_sources.py
git commit -m "feat(import_common): TabularSource protocol + XLSXSource + wykryj_format (Faza 1 T2)"
```

---

### Task 3: `CSVSource` — encoding, delimiter, nagłówek, banned, loc-keys

Nowe źródło CSV: dekodowanie (utf-8-sig → cp1250 → iso-8859-2), detekcja
delimitera (`;` domyślny — polski Excel), nagłówek przez wspólny
`find_similar_row_in_rows`, klucze lokalizacyjne, filtr `banned_names`.

**Files:**
- Modify: `src/import_common/sources.py`
- Test: `src/import_common/tests/test_sources.py`

**Interfaces:**
- Consumes: `find_similar_row_in_rows`, `rename_duplicate_columns`,
  `DEFAULT_BANNED_NAMES` (z `import_common.util`), `HeaderNotFoundException`
  (z `import_common.exceptions`).
- Produces: `class CSVSource` — `__init__(path, *, try_names=None,
  min_points=None, banned_names=None)`, implementuje `TabularSource`. Rzuca
  `HeaderNotFoundException` gdy nagłówka nie ma. Puste linie pomijane.

- [ ] **Step 1: Napisz failing testy**

**Importy dodaj do bloku importów NA GÓRZE pliku** (dobra praktyka; uwaga:
`src/import_common/tests` jest w `extend-exclude` ruff-a, więc lint tego pliku
NIE wymusi — ale trzymamy porządek). Do góry
`src/import_common/tests/test_sources.py` dopisz:

```python
import pytest

from import_common.exceptions import HeaderNotFoundException
from import_common.sources import CSVSource
```

Testy (funkcje + stała) dopisz na końcu pliku:

```python
_CSV_NAGLOWEK = "Numer;Nazwisko;Imię;Orcid;Stanowisko;Nazwa jednostki"


def _zapisz(tmp_path, tresc, encoding="utf-8", nazwa="dane.csv"):
    p = tmp_path / nazwa
    p.write_bytes(tresc.encode(encoding))
    return str(p)


def test_csvsource_srednik_cp1250(tmp_path):
    tresc = (
        f"{_CSV_NAGLOWEK}\n"
        "1;Kowalski;Jan;;Asystent;Katedra Chorób\n"
        "2;Wiśniewska;Zofia;;Adiunkt;Zakład Fizyki\n"
    )
    path = _zapisz(tmp_path, tresc, encoding="cp1250")
    src = CSVSource(path)
    assert src.count() == 2
    wiersze = list(src.data())
    assert wiersze[0]["nazwisko"] == "Kowalski"
    assert wiersze[0]["nazwa_jednostki"] == "Katedra Chorób"
    # klucze lokalizacyjne — CSV to jeden arkusz
    assert wiersze[0]["__xls_loc_sheet__"] == 0
    assert wiersze[1]["__xls_loc_row__"] > wiersze[0]["__xls_loc_row__"]


def test_csvsource_przecinek_delimiter(tmp_path):
    tresc = (
        "Nazwisko,Imię,Nazwa jednostki,Orcid,Stanowisko\n"
        "Nowak,Anna,Katedra Testowa,,Profesor\n"
    )
    path = _zapisz(tmp_path, tresc, encoding="utf-8")
    src = CSVSource(path)
    assert src.count() == 1
    assert list(src.data())[0]["imię"] == "Anna"


def test_csvsource_odrzuca_pesel(tmp_path):
    tresc = (
        "Nazwisko;Imię;PESEL;Nazwa jednostki;Orcid;Stanowisko\n"
        "Kowalski;Jan;12345678901;Katedra;;Asystent\n"
    )
    path = _zapisz(tmp_path, tresc, encoding="utf-8")
    wiersz = list(CSVSource(path).data())[0]
    assert "pesel" not in wiersz


def test_csvsource_brak_naglowka_rzuca(tmp_path):
    tresc = "aaa;bbb;ccc\n1;2;3\n"
    path = _zapisz(tmp_path, tresc, encoding="utf-8")
    with pytest.raises(HeaderNotFoundException):
        CSVSource(path).count()


def test_csvsource_pusty_plik_zero(tmp_path):
    # sam nagłówek, brak danych
    tresc = f"{_CSV_NAGLOWEK}\n"
    path = _zapisz(tmp_path, tresc, encoding="utf-8")
    src = CSVSource(path)
    assert src.count() == 0
    assert list(src.data()) == []


def test_csvsource_pomija_puste_linie(tmp_path):
    tresc = (
        f"{_CSV_NAGLOWEK}\n"
        "1;Kowalski;Jan;;Asystent;Katedra\n"
        "\n"
        ";;;;;\n"
        "2;Nowak;Ewa;;Adiunkt;Zakład\n"
    )
    path = _zapisz(tmp_path, tresc, encoding="utf-8")
    src = CSVSource(path)
    assert src.count() == 2


def test_csvsource_poszarpany_wiersz_zachowuje_loc_keys(tmp_path):
    # wiersz danych KRÓTSZY niż nagłówek (csv.reader nie padduje) — klucze
    # lokalizacyjne muszą i tak powstać na właściwych pozycjach
    tresc = f"{_CSV_NAGLOWEK}\n" "1;Kowalski;Jan\n"  # brak 3 ostatnich kolumn
    path = _zapisz(tmp_path, tresc, encoding="utf-8")
    wiersz = list(CSVSource(path).data())[0]
    assert wiersz["__xls_loc_sheet__"] == 0
    assert wiersz["__xls_loc_row__"] == 1
    assert wiersz["nazwisko"] == "Kowalski"
    # brakujące kolumny → puste, nie przesunięte
    assert wiersz["nazwa_jednostki"] == ""


def test_csvsource_srednik_wygrywa_z_przecinkiem_dziesietnym(tmp_path):
    # §13: plik `;` z przecinkiem dziesiętnym `0,5` w komórce — detekcja NIE
    # może wybrać `,` jako delimitera; komórka „0,5" zostaje w całości
    tresc = (
        "Nazwisko;Imię;Nazwa jednostki;Orcid;Stanowisko;Wymiar etatu\n"
        "Kowalski;Jan;Katedra;;Asystent;0,5\n"
        "Nowak;Ewa;Zakład;;Adiunkt;0,5\n"
    )
    path = _zapisz(tmp_path, tresc, encoding="utf-8")
    src = CSVSource(path)
    assert src.count() == 2
    wiersz = list(src.data())[0]
    assert wiersz["wymiar_etatu"] == "0,5"
    assert wiersz["nazwisko"] == "Kowalski"
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_common/tests/test_sources.py -k csvsource -v`
Expected: FAIL na `ImportError: cannot import name 'CSVSource'`.

- [ ] **Step 3: Implementuj `CSVSource`**

Dopisz do `src/import_common/sources.py` (import u góry pliku + klasa). Na górze
dodaj do importów:

```python
import csv
import io

from django.utils.functional import cached_property

from .exceptions import HeaderNotFoundException
from .util import (
    DEFAULT_BANNED_NAMES,
    XLSImportFile,
    find_similar_row_in_rows,
    rename_duplicate_columns,
)
```

(usuń poprzedni `from .util import XLSImportFile` — zastąpiony powyższym; `csv`,
`io`, `cached_property` dołóż do bloku importów.)

Funkcje pomocnicze i klasa (na końcu pliku):

```python
def _zdekoduj(raw: bytes) -> str:
    """Dekoduje bajty CSV, próbując kolejno: ``utf-8-sig`` (BOM), ``cp1250``
    (Excel na Windows), ``iso-8859-2``. ``utf-8-sig`` jest realnym
    dyskryminatorem: rzuca ``UnicodeDecodeError`` na bajtach spoza UTF-8 (np.
    polskie znaki w cp1250), więc pliki UTF-8 łapią się pierwsze, a cp1250
    dopiero gdy UTF-8 zawiedzie. **Uwaga:** cp1250 dekoduje niemal każdy bajt
    (tylko 5 jest niezdefiniowanych), więc gałąź ``iso-8859-2`` jest w praktyce
    martwa — plik faktycznie w iso-8859-2 zwykle „poprawnie" (bez wyjątku)
    zdekoduje się jako cp1250 z przekłamanymi kilkoma znakami. Rozróżnienie
    cp1250/iso wymagałoby heurystyki częstości znaków — poza zakresem Fazy 1."""
    for enc in ("utf-8-sig", "cp1250", "iso-8859-2"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    # Ostateczność — nie powinno się zdarzyć (cp1250 dekoduje ~wszystko):
    return raw.decode("utf-8", errors="replace")


def _wykryj_delimiter(tekst: str) -> str:
    """Wykrywa delimiter CSV. ``csv.Sniffer`` na pierwszych ~5 liniach, z
    fallbackiem „policz ``;`` vs ``,`` vs tab" (Sniffer bywa kruchy na
    jednokolumnowych plikach). Domyślnie ``;`` — polski Excel."""
    probka = "\n".join(tekst.splitlines()[:5])
    try:
        return csv.Sniffer().sniff(probka, delimiters=";,\t").delimiter
    except csv.Error:
        # Sniffer nie rozpoznał — policz ręcznie:
        liczby = {d: probka.count(d) for d in (";", ",", "\t")}
        najlepszy = max(liczby, key=liczby.get)
        return najlepszy if liczby[najlepszy] > 0 else ";"


class CSVSource:
    """Źródło CSV: detekcja encodingu + delimitera, nagłówek przez wspólny
    ``find_similar_row_in_rows``, klucze lokalizacyjne, filtr ``banned_names``.
    CSV = zawsze JEDEN „arkusz" (``__xls_loc_sheet__ = 0``)."""

    def __init__(
        self, path, *, try_names=None, min_points=None, banned_names=None
    ):
        self.path = path
        self.try_names = try_names
        self.min_points = min_points
        self.banned_names = (
            DEFAULT_BANNED_NAMES if banned_names is None else banned_names
        )

    @cached_property
    def _wiersze(self) -> list[list[str]]:
        with open(self.path, "rb") as f:
            tekst = _zdekoduj(f.read())
        delimiter = _wykryj_delimiter(tekst)
        reader = csv.reader(io.StringIO(tekst), delimiter=delimiter)
        return [list(r) for r in reader]

    @cached_property
    def _naglowek(self):
        res = find_similar_row_in_rows(
            self._wiersze, try_names=self.try_names, min_points=self.min_points
        )
        if res is None:
            raise HeaderNotFoundException(
                "Nie znaleziono wiersza nagłówka w pliku CSV"
            )
        return res

    @staticmethod
    def _pusty(row) -> bool:
        return not any((c or "").strip() for c in row)

    def count(self) -> int:
        _colnames, no = self._naglowek
        total = 0
        for n_row, row in enumerate(self._wiersze):
            if n_row < no:
                continue
            if self._pusty(row):
                continue
            total += 1
        return total

    def data(self) -> Iterator[dict]:
        colnames, no = self._naglowek
        colnames = rename_duplicate_columns(colnames)
        colnames.append("__xls_loc_sheet__")
        colnames.append("__xls_loc_row__")

        for n_row, row in enumerate(self._wiersze):
            if n_row < no:
                continue
            if self._pusty(row):
                continue
            data = list(row[: len(colnames) - 2])
            # CSV bywa „poszarpany": wiersz danych krótszy niż nagłówek.
            # openpyxl padduje do max_column, csv.reader NIE — bez dopadowania
            # zip() przesunąłby klucze lokalizacyjne na nazwy kolumn danych, a
            # __xls_loc_* nie powstałyby (→ TypeError w XLSParseError.__str__ i
            # NULL w sortowaniu get_details_set). Dopaduj do liczby kolumn danych:
            data += [""] * (len(colnames) - 2 - len(data))
            data.append(0)  # __xls_loc_sheet__ (CSV = jeden arkusz)
            data.append(n_row)  # __xls_loc_row__ (0-based, jak XLSImportFile)

            yld = dict(zip(colnames, data, strict=False))
            for banned_name in self.banned_names:
                yld.pop(banned_name, None)
            yield yld
```

**Uwaga o `no`:** `find_similar_row_in_rows` zwraca `n` **1-based** (jak
`find_similar_row`). Nagłówek 1-based `no` = index 0-based `no-1`; wiersze
danych zaczynają się od 0-based `no`. Warunek `if n_row < no: continue` (gdzie
`n_row` jest 0-based z `enumerate`) pomija indeksy `0..no-1` (włącznie z
nagłówkiem) — identycznie jak `XLSImportFile.data()`.

- [ ] **Step 4: Uruchom — zielone**

Run: `uv run pytest src/import_common/tests/test_sources.py -v`
Expected: PASS wszystkie (Task 2 + Task 3).

- [ ] **Step 5: Commit**

```bash
git add src/import_common/sources.py src/import_common/tests/test_sources.py
git commit -m "feat(import_common): CSVSource — encoding/delimiter/nagłówek/banned (Faza 1 T3)"
```

---

### Task 4: `parsers/wartosci.py` — normalizacja dat (CSV `DD.MM.YYYY`)

CSV daje daty jako stringi. `ExcelDateField` obsługuje datetime (XLSX/openpyxl) i
ISO `YYYY-MM-DD` (Django default), ale **nie** polskie `DD.MM.YYYY`. Ta warstwa
stoi nad źródłem i normalizuje daty przed walidacją formularzem.

**Files:**
- Create: `src/import_pracownikow/parsers/__init__.py`
- Create: `src/import_pracownikow/parsers/wartosci.py`
- Create: `src/import_pracownikow/tests/test_parsers/__init__.py`
- Create: `src/import_pracownikow/tests/test_parsers/test_wartosci.py`

**Interfaces:**
- Produces:
  - `normalize_date_pl(value) -> date | Any` — datetime/date → `date`; string
    `DD.MM.YYYY` → `date`; wszystko inne (ISO, puste, nie-data) zwrócone **bez
    zmian** (walidację/odrzucenie zostawiamy `ExcelDateField`).
  - `normalizuj_wartosci_wiersza(elem: dict) -> dict` — kopia `elem` z
    znormalizowanymi kluczami dat (`data_zatrudnienia`,
    `data_końca_zatrudnienia`).

- [ ] **Step 1: Napisz failing testy**

Utwórz `src/import_pracownikow/tests/test_parsers/__init__.py` (pusty) oraz
`src/import_pracownikow/tests/test_parsers/test_wartosci.py`:

```python
from datetime import date, datetime

import pytest

from import_pracownikow.parsers.wartosci import (
    normalize_date_pl,
    normalizuj_wartosci_wiersza,
)


@pytest.mark.parametrize(
    "wejscie,oczekiwane",
    [
        ("01.10.2016", date(2016, 10, 1)),  # polski DD.MM.YYYY
        ("2016-10-01", "2016-10-01"),  # ISO — zostaw dla ExcelDateField
        (datetime(2016, 10, 1, 12, 0), date(2016, 10, 1)),  # XLSX datetime
        (date(2016, 10, 1), date(2016, 10, 1)),  # date bez zmian
        ("", ""),  # puste — bez zmian
        ("cokolwiek", "cokolwiek"),  # nie-data — bez zmian (form odrzuci)
        (None, None),
    ],
)
def test_normalize_date_pl(wejscie, oczekiwane):
    assert normalize_date_pl(wejscie) == oczekiwane


def test_normalizuj_wartosci_wiersza_tylko_daty():
    elem = {
        "nazwisko": "Kowalski",
        "data_zatrudnienia": "01.10.2016",
        "data_końca_zatrudnienia": "",
        "wymiar_etatu": "1,0",
    }
    out = normalizuj_wartosci_wiersza(elem)
    assert out["data_zatrudnienia"] == date(2016, 10, 1)
    assert out["data_końca_zatrudnienia"] == ""  # puste bez zmian
    assert out["nazwisko"] == "Kowalski"  # nietknięte
    assert out["wymiar_etatu"] == "1,0"  # nie-data nietknięta
    # nie mutuje wejścia
    assert elem["data_zatrudnienia"] == "01.10.2016"
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_pracownikow/tests/test_parsers/test_wartosci.py -v`
Expected: FAIL na `ModuleNotFoundError: ...parsers.wartosci`.

- [ ] **Step 3: Implementuj**

Utwórz `src/import_pracownikow/parsers/__init__.py` (pusty) i
`src/import_pracownikow/parsers/wartosci.py`:

```python
"""Normalizacja wartości komórek nad warstwą źródła (CSV + XLSX).

CSV daje wartości jako stringi tam, gdzie XLSX (openpyxl) daje typy natywne
(``datetime`` dla dat). ``ExcelDateField`` obsługuje ``datetime`` i ISO
``YYYY-MM-DD``, ale nie polskie ``DD.MM.YYYY`` — tę lukę zamyka
``normalize_date_pl``. Warstwa jest specyficzna dla importu pracowników
(zna nazwy kolumn-dat), więc siedzi w ``import_pracownikow.parsers``, nie w
generycznym ``import_common``.
"""

from datetime import date, datetime

# Kolumny-daty w rygorystycznym schemacie Fazy 0/1 (nazwy = znormalizowane
# nagłówki wzorca BPP). Faza 2 (mapowanie) uczyni to konfigurowalnym.
_KLUCZE_DAT = ("data_zatrudnienia", "data_końca_zatrudnienia")


def normalize_date_pl(value):
    """datetime/date → ``date``; string ``DD.MM.YYYY`` → ``date``; wszystko
    inne (ISO, puste, nie-data) zwrócone bez zmian — walidację/odrzucenie
    zostawiamy ``ExcelDateField``. Kropka jednoznacznie sygnalizuje zapis
    europejski, więc nie kolidujemy z ``%m/%d/%Y`` z Django defaults."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        s = value.strip()
        if s:
            try:
                return datetime.strptime(s, "%d.%m.%Y").date()
            except ValueError:
                # nie DD.MM.YYYY (może ISO, może śmieć) — zostaw formularzowi
                return value
    return value


def normalizuj_wartosci_wiersza(elem: dict) -> dict:
    """Zwraca KOPIĘ ``elem`` ze znormalizowanymi kolumnami-datami. Nie mutuje
    wejścia (audyt ``dane_z_xls`` musi zachować surowe wartości)."""
    out = dict(elem)
    for klucz in _KLUCZE_DAT:
        if out.get(klucz) is not None:
            out[klucz] = normalize_date_pl(out[klucz])
    return out
```

- [ ] **Step 4: Uruchom — zielone**

Run: `uv run pytest src/import_pracownikow/tests/test_parsers/test_wartosci.py -v`
Expected: PASS (7 przypadków parametrów + 1 test dict = 8 testów).

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/parsers/ src/import_pracownikow/tests/test_parsers/
git commit -m "feat(import_pracownikow): normalizacja dat DD.MM.YYYY nad źródłem (Faza 1 T4)"
```

---

### Task 5: Fabryka `otworz_zrodlo` + podpięcie do `analizuj()`

Fabryka wykrywa format i zwraca właściwe źródło; `analizuj()` przełącza się z
`XLSImportFile` na fabrykę i normalizuje wartości wiersza. Aktualizacja 3
istniejących testów `analyze` (patch celu).

**Files:**
- Modify: `src/import_common/sources.py` (dodaj `otworz_zrodlo`)
- Modify: `src/import_pracownikow/pipeline/analyze.py:32,172-176`
- Modify: `src/import_pracownikow/tests/test_pipeline/test_analyze.py:37,75,110`
- Test: `src/import_common/tests/test_sources.py` (test fabryki)

**Interfaces:**
- Consumes: `wykryj_format`, `XLSXSource`, `CSVSource`.
- Produces: `otworz_zrodlo(path, *, try_names=None, min_points=None,
  banned_names=None) -> TabularSource`.

- [ ] **Step 1: Napisz failing test fabryki**

Do bloku importów **na górze** `src/import_common/tests/test_sources.py` dodaj
`otworz_zrodlo` do istniejącej linii importu z `import_common.sources`
(np. `from import_common.sources import CSVSource, XLSXSource, otworz_zrodlo,
wykryj_format`). Testy dopisz na końcu pliku:

```python
def test_otworz_zrodlo_xlsx(default_xlsx):
    assert isinstance(otworz_zrodlo(default_xlsx), XLSXSource)


def test_otworz_zrodlo_csv(tmp_path):
    p = tmp_path / "dane.csv"
    p.write_text("Nazwisko;Imię\nKowalski;Jan\n", encoding="utf-8")
    assert isinstance(otworz_zrodlo(str(p)), CSVSource)
```

- [ ] **Step 2: Uruchom — czerwone**

Run: `uv run pytest src/import_common/tests/test_sources.py -k otworz_zrodlo -v`
Expected: FAIL na `ImportError: cannot import name 'otworz_zrodlo'`.

- [ ] **Step 3: Dodaj fabrykę do `sources.py`**

Dopisz na końcu `src/import_common/sources.py`:

```python
def otworz_zrodlo(
    path, *, try_names=None, min_points=None, banned_names=None
) -> TabularSource:
    """Wykrywa format pliku (magic-bytes) i zwraca właściwe źródło —
    ``XLSXSource`` albo ``CSVSource`` — z tym samym kontraktem
    (``count()`` + ``data()``)."""
    klasa = XLSXSource if wykryj_format(path) == "xlsx" else CSVSource
    return klasa(
        path,
        try_names=try_names,
        min_points=min_points,
        banned_names=banned_names,
    )
```

- [ ] **Step 4: Uruchom — zielone (fabryka)**

Run: `uv run pytest src/import_common/tests/test_sources.py -v`
Expected: PASS wszystkie.

- [ ] **Step 5: Podepnij fabrykę + normalizację w `analyze.py`**

W `src/import_pracownikow/pipeline/analyze.py` popraw importy tak, by NIE złamać
isort (`I001` jest w `select`), robiąc DWIE osobne zmiany:

1. Zamień linię 32 `from import_common.util import XLSImportFile` na
   `from import_common.sources import otworz_zrodlo` (poprawna pozycja
   alfabetyczna w grupie `import_common.*`: core → exceptions → normalization →
   sources; `XLSImportFile` nie jest już używany, więc go usuwamy).
2. Dopisz `from import_pracownikow.parsers.wartosci import
   normalizuj_wartosci_wiersza` **PO** bloku `from import_pracownikow.models
   import (...)` (linie 33-38) — `models` < `parsers` alfabetycznie, więc musi
   być za nim, nie przed.

Blok importów `import_pracownikow.*` po zmianie:

```python
from import_pracownikow.models import (
    AutorForm,
    ImportPracownikow,
    ImportPracownikowRow,
    JednostkaForm,
)
from import_pracownikow.parsers.wartosci import normalizuj_wartosci_wiersza
```

Zamień treść `analizuj()` — początek funkcji:

```python
def analizuj(parent, p):
    xif = XLSImportFile(parent.plik_xls.path)
    total = xif.count()
    if total == 0:
        raise ValueError("Plik nie zawiera danych do importu (0 wierszy).")

    for elem in p.track(list(xif.data()), total=total, label="Wczytywanie"):
        _przetworz_wiersz(parent, elem)
```

na:

```python
def analizuj(parent, p):
    zrodlo = otworz_zrodlo(parent.plik_xls.path)
    total = zrodlo.count()
    if total == 0:
        raise ValueError("Plik nie zawiera danych do importu (0 wierszy).")

    for elem in p.track(list(zrodlo.data()), total=total, label="Wczytywanie"):
        _przetworz_wiersz(parent, elem)
```

(fabryka zamiast `XLSImportFile`; `_przetworz_wiersz` dostaje **surowy** `elem`.)

**Normalizację wartości robimy WEWNĄTRZ `_przetworz_wiersz`** — bo `dane_z_xls`
(audyt) musi zostać surowe, a znormalizowane wartości idą tylko do formularzy.
W `_przetworz_wiersz` dodaj na początku funkcji (przed `JednostkaForm`)
wyliczenie znormalizowanego dictu i zamień źródło danych **formularzy** na niego
(NIE tykaj `dane_z_xls=elem` — zostaje surowe):

```python
def _przetworz_wiersz(parent, elem):
    dane_form = normalizuj_wartosci_wiersza(elem)
    jednostka_form = JednostkaForm(data=dane_form)
```

oraz niżej w tej samej funkcji zamień budowę `autor_form`:

```python
    autor_form = AutorForm(data=dane_form)
```

Pozostałe użycia `elem` w `_przetworz_wiersz` (`dane_z_xls=elem`,
`normalize_nullboleanfield(elem.get("podstawowe_miejsce_pracy"))`, argumenty
`XLSParseError(elem, ...)`/`XLSMatchError(elem, ...)`) **zostają na surowym
`elem`** — audyt i komunikaty błędów mają widzieć to, co było w pliku.
(Normalizacja dotyka tylko dat, więc boolean `podstawowe_miejsce_pracy` i tak
jest identyczny.)

- [ ] **Step 6: Zaktualizuj 3 istniejące testy `test_analyze.py`**

W `src/import_pracownikow/tests/test_pipeline/test_analyze.py` zrób **globalny
rename w całym pliku** (dotyczy 3 testów, w tym `test_pusty_plik_rzuca_jawny_blad`,
który używa innego kształtu bloku niż dwa pozostałe):
- każde `import_pracownikow.pipeline.analyze.XLSImportFile` → 
  `import_pracownikow.pipeline.analyze.otworz_zrodlo`
- każde `MockXIF` → `MockZrodlo`

Interfejs źródła jest identyczny (`count()`/`data()`), więc `.return_value`,
`inst.count.return_value`, `inst.data.return_value` zostają bez zmian.

- [ ] **Step 7: Uruchom — zielone (pipeline + analyze)**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/ -v`
Expected: PASS wszystkie (3 zaktualizowane `test_analyze` + `test_integrate`).

- [ ] **Step 8: Commit**

```bash
git add src/import_common/sources.py src/import_common/tests/test_sources.py \
  src/import_pracownikow/pipeline/analyze.py \
  src/import_pracownikow/tests/test_pipeline/test_analyze.py
git commit -m "feat(import_pracownikow): analizuj() przez otworz_zrodlo + normalizacja wartości (Faza 1 T5)"
```

---

### Task 6: Test end-to-end CSV przez `analizuj()` + newsfragment

Dowód, że CSV działa przez pełną fazę analizy (nie tylko na poziomie źródła):
realny plik CSV `;`/cp1250 z datą `DD.MM.YYYY` → wiersze zmatchowane, `stan`
przeanalizowany, autor/jednostka rozpoznani. Plus newsfragment.

**Files:**
- Create: `src/import_pracownikow/tests/test_pipeline/test_analyze_csv.py`
- Create: `src/bpp/newsfragments/import-pracownikow-csv-zrodla.feature.rst`

**Interfaces:**
- Consumes: `analizuj` (Faza 0), fixtures `admin_user` (pytest-django),
  `dwa_autory_z_jednostka` (conftest Fazy 0), `otworz_zrodlo` (Task 5).

- [ ] **Step 1: Napisz test end-to-end (czerwony do implementacji T1-T5)**

Utwórz `src/import_pracownikow/tests/test_pipeline/test_analyze_csv.py`:

```python
"""End-to-end: plik CSV (polski Excel: ``;`` + cp1250 + data DD.MM.YYYY)
przez pełną fazę analizy. Weryfikuje, że warstwa źródeł + normalizacja dat
spinają się z pipeline'em Fazy 0 (matchowanie autora/jednostki, dry-run)."""

from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from liveops.testing import MockProgress

from import_common.exceptions import HeaderNotFoundException
from import_pracownikow.models import ImportPracownikow


def _csv_bytes(nazwisko, imie, jednostka):
    tresc = (
        "Numer;Nazwisko;Imię;Orcid;Tytuł/Stopień;Stanowisko;"
        "Grupa pracownicza;Nazwa jednostki;Wydział;Data zatrudnienia;"
        "Wymiar etatu;Podstawowe miejsce pracy\n"
        f"1;{nazwisko};{imie};;dr;Asystent;Badawczo-dydaktyczna;"
        f"{jednostka};Wydział Testowy;01.10.2016;Pełny etat;TAK\n"
    )
    return tresc.encode("cp1250")


@pytest.mark.django_db
def test_analiza_csv_end_to_end(admin_user, dwa_autory_z_jednostka):
    autor, jednostka = dwa_autory_z_jednostka
    imp = ImportPracownikow(owner=admin_user, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls = SimpleUploadedFile(
        "pracownicy.csv",
        _csv_bytes(autor.nazwisko, autor.imiona, jednostka.nazwa),
    )
    imp.save()

    from import_pracownikow.pipeline.analyze import analizuj

    analizuj(imp, MockProgress(imp))

    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_PRZEANALIZOWANY
    row = imp.importpracownikowrow_set.get()
    # źródło CSV rozpoznane, autor i jednostka zmatchowani:
    assert row.autor_id == autor.pk
    assert row.jednostka_id == jednostka.pk
    # data DD.MM.YYYY sparsowana. UWAGA: dane_znormalizowane to
    # JSONField(encoder=DjangoJSONEncoder) — date serializuje się do stringa
    # "2016-10-01" i po refresh_from_db JEST stringiem. Property
    # dane_bardziej_znormalizowane parsuje go z powrotem na date (models.py:193).
    assert row.dane_bardziej_znormalizowane["data_zatrudnienia"] == date(2016, 10, 1)


@pytest.mark.django_db
def test_analiza_csv_bez_naglowka_rzuca(admin_user):
    # kontrakt §13: CSV bez wykrywalnego nagłówka → jawny HeaderNotFoundException
    # (asymetria wobec XLSX, który daje ValueError "0 wierszy" — udokumentowana
    # w sekcji „Poza zakresem"). Błąd propaguje przez analizuj() jako traceback.
    imp = ImportPracownikow(owner=admin_user, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls = SimpleUploadedFile("zle.csv", b"aaa;bbb;ccc\n1;2;3\n")
    imp.save()

    from import_pracownikow.pipeline.analyze import analizuj

    with pytest.raises(HeaderNotFoundException):
        analizuj(imp, MockProgress(imp))
```

- [ ] **Step 2: Uruchom — zielone (po T1-T5 spójne end-to-end)**

Run: `uv run pytest src/import_pracownikow/tests/test_pipeline/test_analyze_csv.py -v`
Expected: PASS. Jeśli FAIL na dacie → sprawdź, że `normalizuj_wartosci_wiersza`
jest wołane w `analizuj()` (Task 5 Step 5).

- [ ] **Step 3: Newsfragment**

Utwórz `src/bpp/newsfragments/import-pracownikow-csv-zrodla.feature.rst`:

```rst
Import pracowników przyjmuje teraz pliki **CSV** (obok XLSX) — z automatycznym
wykrywaniem formatu, kodowania (UTF-8/CP1250) i separatora (``;``/``,``/tab).
```

- [ ] **Step 4: Pełna regresja aplikacji importu + współdzielonego import_common**

Run: `uv run pytest src/import_pracownikow/ src/import_common/ -q`
Expected: PASS wszystko (Faza 0 + Faza 1 + backward-compat).

- [ ] **Step 5: Ruff**

Run: `ruff format src/import_common/ src/import_pracownikow/ && ruff check src/import_common/ src/import_pracownikow/`
Expected: brak błędów.

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/tests/test_pipeline/test_analyze_csv.py \
  src/bpp/newsfragments/import-pracownikow-csv-zrodla.feature.rst
git commit -m "test(import_pracownikow): end-to-end CSV + newsfragment (Faza 1 T6)"
```

---

## Self-Review (autor planu)

**Spec coverage (§5):**
- CSV + XLSX przez `TabularSource` → T2/T3 ✅
- Detekcja formatu po magic-bytes (nie rozszerzeniu) → `wykryj_format` T2 ✅
- Encoding utf-8-sig → cp1250 → iso-8859-2 → `_zdekoduj` T3 ✅
- Delimiter Sniffer + fallback, domyślnie `;` → `_wykryj_delimiter` T3 ✅
- Fuzzy-header format-agnostyczny (`find_similar_row_in_rows`, `normalize_cell_header`
  na surowej wartości) → T1 ✅
- Klucze `__xls_loc_sheet__`/`__xls_loc_row__` w CSV → T3 ✅
- `DEFAULT_BANNED_NAMES` (pesel) w CSV → T3 ✅
- Normalizacja wartości nad źródłem (daty) → T4 ✅
- Backward compat (`znajdz_naglowek`, `XLSImportFile`, `import_dyscyplin`) → T1
  wrapper + regresja T1 Step 5 ✅

**Świadomie poza Fazą 1 (udokumentowane w „Poza zakresem"):** mapowanie kolumn,
spójność nagłówków między arkuszami XLSX, jawny błąd braku nagłówka dla XLSX,
parser sklejonej osoby, wskaźnik pewności.

**Placeholder scan:** brak TBD/TODO; każdy krok kodu ma pełną treść.

**Type consistency:** `count()`/`data()` identyczne w `XLSXSource`, `CSVSource`,
`otworz_zrodlo`. `find_similar_row_in_rows` zwraca `(list[str], int)` — spójnie
konsumowane w `CSVSource._naglowek`. `normalize_date_pl` zwraca `date` lub
wejście bez zmian — testy T4 pokrywają oba warianty; `ExcelDateField` domyka ISO.

**Recenzje (subagent Fable, 2 iteracje):** iter1 — 11 findingów (2 krytyczne testy
nigdy-nie-przechodzące, 4 ważne correctness/zakres, 5 drobnych) — wszystkie
naniesione. iter2 — zweryfikował poprawki iter1 na rzeczywistym kodzie (bezbłędne)
+ 2 ważne ruff-gate (martwy import `Worksheet` F401, kolejność importów I001) +
3 drobne — wszystkie naniesione. Werdykt iter2: gotów do implementacji.
