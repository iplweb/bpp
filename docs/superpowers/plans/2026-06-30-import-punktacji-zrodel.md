# Import punktacji źródeł z JCR — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nowa aplikacja `import_punktacji_zrodel` wczytuje plik JCR (Clarivate
Journal Citation Reports) w formacie XLSX/CSV, dopasowuje czasopisma do
`Zrodlo`, pokazuje podgląd rozbieżności (Impact Factor + kwartyl Web of
Science) na poziomie źródła i po potwierdzeniu zapisuje je do
`Punktacja_Zrodla`.

**Architecture:** Cienka aplikacja na frameworku `long_running`
(`Operation` + celery + strony progress/results), wzorowana na
`import_list_ministerialnych`. Czysty parser (bez ORM) → logika
porównania/zapisu w `core.py` (dry-run vs commit) → widoki/formularz/szablony
analogiczne do siblinga. Poziom prac/publikacji reużywa istniejącego appa
`rozbieznosci` (tylko linki).

**Tech Stack:** Python ≥3.10, Django, `long_running`, `import_common`
(`matchuj_zrodlo`), `openpyxl`, stdlib `csv`, crispy-forms-foundation, pytest
+ model_bakery, towncrier.

## Global Constraints

- **`uv run`** przed KAŻDYM poleceniem Pythona (`uv run pytest`,
  `uv run python src/manage.py …`). Nigdy gołe `python`.
- **Max 88 znaków/linia** (ruff). `ruff format .` + `ruff check .` (bez
  `--fix`; problemy fiksuj ręcznie).
- **Nie modyfikować istniejących migracji.** Nowa migracja OK.
- **Baseline NIE jest aktualizowany** (`make baseline-update`/rebuild — NIE).
- **Bez nazw handlowych w UI** (etykiety: bez „impact factor"/„JCR"/„WoS";
  używaj „punktacja źródeł", „wskaźnik IF"/„IF", „kwartyl"). W kodzie/docach
  nazwy formatu dozwolone.
- **Newsfragment `.rst`** (orphan `+fd388.feature.rst`), nie `.md`.
- **Uprawnienia:** grupa `"wprowadzanie danych"` (`GroupRequiredMixin`).
- **Worktree:** `~/Programowanie/bpp-fix-fd388-import-punktacji-zrodel`
  (gałąź `fix-fd388-import-punktacji-zrodel`). Wszystkie polecenia z tego
  katalogu.
- **PR referuje** `Fixes Freshdesk FD#388` +
  `https://iplweb.freshdesk.com/a/tickets/388`.
- Spec źródłowy:
  `docs/superpowers/specs/2026-06-30-import-punktacji-zrodel-design.md`.
- Fixtures są już w repo: `src/import_punktacji_zrodel/tests/testdata/
  jcr_fd388.xlsx` i `…/jcr_fd388.csv`.

## File Structure

```
src/import_punktacji_zrodel/
  __init__.py
  apps.py                      # ImportPunktacjiZrodelConfig
  parser.py                    # czysty parser JCR (XLSX/CSV) → ParsedJCR
  models.py                    # ImportPunktacjiZrodel + WierszImportuPunktacjiZrodel
  core.py                      # analyze_jcr_file(path, parent)
  forms.py                     # NowyImportForm
  views.py                     # widoki long_running + ZatwierdzImportView
  urls.py                      # app_name=import_punktacji_zrodel
  admin.py                     # (puste/minimalne — spójne z siblingami)
  migrations/__init__.py
  migrations/0001_initial.py   # wygenerowana (makemigrations)
  templates/import_punktacji_zrodel/
    importpunktacjizrodel_form.html
    importpunktacjizrodel_list.html
    importpunktacjizrodel_detail.html
    wierszimportupunktacjizrodel_list.html
  tests/
    __init__.py
    conftest.py                # fixtures: ścieżki do plików, baker Zrodlo
    testdata/jcr_fd388.xlsx    # (już w repo)
    testdata/jcr_fd388.csv     # (już w repo)
    test_parser.py
    test_core.py
    test_views.py
    test_repro_fd388.py
```

Modyfikowane pliki istniejące:
- `src/django_bpp/settings/base.py` — `INSTALLED_APPS` (jedna lista ~L356).
- `pyproject.toml` — `[tool.setuptools.packages.find].include` (~L179–206).
- `src/django_bpp/urls.py` — `include("import_punktacji_zrodel.urls")`.
- `src/django_bpp/templates/top_bar.html` — menu (prawa kolumna).
- `src/bpp/newsfragments/+fd388.feature.rst` — nowy.

---

### Task 1: Scaffolding aplikacji + rejestracja

**Files:**
- Create: `src/import_punktacji_zrodel/__init__.py` (pusty)
- Create: `src/import_punktacji_zrodel/apps.py`
- Create: `src/import_punktacji_zrodel/migrations/__init__.py` (pusty)
- Create: `src/import_punktacji_zrodel/tests/__init__.py` (pusty)
- Modify: `src/django_bpp/settings/base.py` (INSTALLED_APPS)
- Modify: `pyproject.toml` (`[tool.setuptools.packages.find].include`)

**Interfaces:**
- Produces: zarejestrowana aplikacja Django `import_punktacji_zrodel`
  (app_label `import_punktacji_zrodel`).

- [ ] **Step 1: apps.py**

```python
from django.apps import AppConfig


class ImportPunktacjiZrodelConfig(AppConfig):
    name = "import_punktacji_zrodel"
    verbose_name = "Import punktacji źródeł"
    default_auto_field = "django.db.models.BigAutoField"
```

- [ ] **Step 2: Dopisz do INSTALLED_APPS**

W `src/django_bpp/settings/base.py`, w jedynej liście `INSTALLED_APPS = [`
(~L356), obok pozostałych `import_*` (po linii z
`"import_list_ministerialnych",`) dodaj:

```python
    "import_punktacji_zrodel",
```

- [ ] **Step 3: Dopisz do pyproject packages.find.include**

W `pyproject.toml`, w `[tool.setuptools.packages.find]` w liście `include`
(~L179–206), obok innych `import_*` dodaj:

```toml
    "import_punktacji_zrodel",
```

- [ ] **Step 4: Utwórz puste `__init__.py`**

```bash
mkdir -p src/import_punktacji_zrodel/migrations src/import_punktacji_zrodel/tests
touch src/import_punktacji_zrodel/__init__.py \
      src/import_punktacji_zrodel/migrations/__init__.py \
      src/import_punktacji_zrodel/tests/__init__.py
```

- [ ] **Step 5: Sprawdź, że Django widzi aplikację**

Run: `uv run python src/manage.py check 2>&1 | tail -5`
Expected: `System check identified no issues` (lub bez błędów dot. tej app;
„no migrations" ostrzeżenia są OK — model dodamy w Task 3).

- [ ] **Step 6: Commit**

```bash
git add src/import_punktacji_zrodel/__init__.py \
        src/import_punktacji_zrodel/apps.py \
        src/import_punktacji_zrodel/migrations/__init__.py \
        src/import_punktacji_zrodel/tests/__init__.py \
        src/django_bpp/settings/base.py pyproject.toml
git commit -m "feat(import_punktacji_zrodel): scaffold aplikacji + rejestracja (FD#388)"
```

---

### Task 2: Parser JCR (czysty, bez ORM)

**Files:**
- Create: `src/import_punktacji_zrodel/parser.py`
- Create: `src/import_punktacji_zrodel/tests/conftest.py`
- Test: `src/import_punktacji_zrodel/tests/test_parser.py`

**Interfaces:**
- Produces:
  - `@dataclass CzasopismoJCR(nazwa: str, issn: str|None, e_issn: str|None,
    impact_factor: Decimal|None, kwartyl_wos: int|None,
    kategorie: list[tuple[str, int|None]])`
  - `@dataclass ParsedJCR(rok: int|None, czasopisma: list[CzasopismoJCR])`
  - `wczytaj_plik_jcr(path: str) -> ParsedJCR` — wybór czytnika po
    rozszerzeniu (`.csv` → csv, inaczej openpyxl).

- [ ] **Step 1: conftest.py z fixturami ścieżek**

```python
from pathlib import Path

import pytest

TESTDATA = Path(__file__).parent / "testdata"


@pytest.fixture
def jcr_xlsx_path():
    return str(TESTDATA / "jcr_fd388.xlsx")


@pytest.fixture
def jcr_csv_path():
    return str(TESTDATA / "jcr_fd388.csv")
```

- [ ] **Step 2: Napisz failing testy parsera**

`src/import_punktacji_zrodel/tests/test_parser.py`:

```python
from decimal import Decimal

import pytest

from import_punktacji_zrodel.parser import wczytaj_plik_jcr


@pytest.mark.parametrize("fmt", ["xlsx", "csv"])
def test_wykrywa_rok(fmt, jcr_xlsx_path, jcr_csv_path):
    path = jcr_xlsx_path if fmt == "xlsx" else jcr_csv_path
    parsed = wczytaj_plik_jcr(path)
    assert parsed.rok == 2025


@pytest.mark.parametrize("fmt", ["xlsx", "csv"])
def test_licznosc_czasopism_136(fmt, jcr_xlsx_path, jcr_csv_path):
    path = jcr_xlsx_path if fmt == "xlsx" else jcr_csv_path
    parsed = wczytaj_plik_jcr(path)
    assert len(parsed.czasopisma) == 136


@pytest.mark.parametrize("fmt", ["xlsx", "csv"])
def test_pomija_stopke_clarivate(fmt, jcr_xlsx_path, jcr_csv_path):
    path = jcr_xlsx_path if fmt == "xlsx" else jcr_csv_path
    parsed = wczytaj_plik_jcr(path)
    nazwy = [c.nazwa for c in parsed.czasopisma]
    assert not any("Clarivate" in n for n in nazwy)
    assert not any("Terms of Use" in n for n in nazwy)


def test_lancet_wartosci(jcr_xlsx_path):
    parsed = wczytaj_plik_jcr(jcr_xlsx_path)
    lancet = next(c for c in parsed.czasopisma if c.nazwa == "LANCET")
    assert lancet.issn == "0140-6736"
    assert lancet.e_issn == "1474-547X"
    assert lancet.impact_factor == Decimal("109.0")
    assert lancet.kwartyl_wos == 1  # Q1


def test_najlepszy_kwartyl_przy_wielu_kategoriach(jcr_xlsx_path):
    # ISSN 0268-3369 (BONE MARROW TRANSPLANTATION) ma Q1,Q2,Q1,Q1 -> min=1
    parsed = wczytaj_plik_jcr(jcr_xlsx_path)
    bmt = next(c for c in parsed.czasopisma if c.issn == "0268-3369")
    assert bmt.kwartyl_wos == 1
    assert len(bmt.kategorie) >= 2


def test_na_w_issn_daje_none(jcr_xlsx_path):
    # "Nature Cancer": ISSN N/A, eISSN 2662-1347
    parsed = wczytaj_plik_jcr(jcr_xlsx_path)
    nc = next(c for c in parsed.czasopisma if c.nazwa == "Nature Cancer")
    assert nc.issn is None
    assert nc.e_issn == "2662-1347"


def test_elife_same_na(jcr_xlsx_path):
    parsed = wczytaj_plik_jcr(jcr_xlsx_path)
    elife = next(c for c in parsed.czasopisma if c.nazwa == "eLife")
    assert elife.impact_factor is None
    assert elife.kwartyl_wos is None


def test_csv_xlsx_parity(jcr_xlsx_path, jcr_csv_path):
    x = wczytaj_plik_jcr(jcr_xlsx_path)
    c = wczytaj_plik_jcr(jcr_csv_path)
    assert x.rok == c.rok
    assert len(x.czasopisma) == len(c.czasopisma)
    kx = {(z.issn, z.e_issn, z.nazwa) for z in x.czasopisma}
    kc = {(z.issn, z.e_issn, z.nazwa) for z in c.czasopisma}
    assert kx == kc
```

- [ ] **Step 3: Uruchom — ma PAŚĆ**

Run: `uv run pytest src/import_punktacji_zrodel/tests/test_parser.py -q`
Expected: FAIL (`ModuleNotFoundError: import_punktacji_zrodel.parser`).

- [ ] **Step 4: Zaimplementuj parser.py**

```python
"""Czysty parser pliku JCR (Clarivate Journal Citation Reports).

Bez zależności od Django ORM — łatwy do testów jednostkowych.
Obsługuje XLSX (openpyxl) oraz CSV (stdlib csv).
"""

import csv
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

KWARTYL_MAP = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}

_ROK_JIF_RE = re.compile(r"^\s*(\d{4})\s+JIF\s*$")
_ROK_META_RE = re.compile(r"Selected JCR Year:\s*(\d{4})")
_FOOTER_MARKERS = ("Clarivate", "Terms of Use")

_COL_NAZWA = "Journal name"
_COL_ISSN = "ISSN"
_COL_EISSN = "eISSN"
_COL_KATEGORIA = "Category"
_COL_KWARTYL = "JIF Quartile"


@dataclass
class CzasopismoJCR:
    nazwa: str
    issn: str | None
    e_issn: str | None
    impact_factor: Decimal | None
    kwartyl_wos: int | None
    kategorie: list[tuple[str, int | None]] = field(default_factory=list)


@dataclass
class ParsedJCR:
    rok: int | None
    czasopisma: list[CzasopismoJCR]


def _clean(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if s == "" or s.upper() == "N/A":
        return None
    return s


def _parse_if(v) -> Decimal | None:
    s = _clean(v)
    if s is None:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _parse_kwartyl(v) -> int | None:
    s = _clean(v)
    if s is None:
        return None
    return KWARTYL_MAP.get(s.upper())


def _iter_rows_xlsx(path: str):
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.active
        for row in ws.iter_rows(values_only=True):
            yield list(row)
    finally:
        wb.close()


def _iter_rows_csv(path: str):
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            yield row


def _find_header_index(rows: list[list]) -> int:
    for i, row in enumerate(rows):
        cells = [str(c).strip() if c is not None else "" for c in row]
        if _COL_NAZWA in cells and _COL_KWARTYL in cells:
            return i
    raise ValueError("Nie znaleziono wiersza nagłówka w pliku JCR")


def _detect_rok(header: list[str], rows_before: list[list]) -> int | None:
    for cell in header:
        m = _ROK_JIF_RE.match(str(cell or ""))
        if m:
            return int(m.group(1))
    for row in rows_before:
        for cell in row:
            m = _ROK_META_RE.search(str(cell or ""))
            if m:
                return int(m.group(1))
    return None


def wczytaj_plik_jcr(path: str) -> ParsedJCR:
    if path.lower().endswith(".csv"):
        rows = list(_iter_rows_csv(path))
    else:
        rows = list(_iter_rows_xlsx(path))

    hidx = _find_header_index(rows)
    header = [str(c).strip() if c is not None else "" for c in rows[hidx]]
    rok = _detect_rok(header, rows[:hidx])

    idx = {name: i for i, name in enumerate(header)}
    i_nazwa = idx[_COL_NAZWA]
    i_issn = idx.get(_COL_ISSN)
    i_eissn = idx.get(_COL_EISSN)
    i_kat = idx.get(_COL_KATEGORIA)
    i_kw = idx[_COL_KWARTYL]
    i_if = next(
        (i for i, c in enumerate(header) if _ROK_JIF_RE.match(c)), None
    )

    def _cell(row, i):
        if i is None or i >= len(row):
            return None
        return row[i]

    grupy: dict[tuple, CzasopismoJCR] = {}
    for row in rows[hidx + 1 :]:
        nazwa = _clean(_cell(row, i_nazwa))
        if nazwa is None or any(m in str(nazwa) for m in _FOOTER_MARKERS):
            continue
        issn = _clean(_cell(row, i_issn))
        e_issn = _clean(_cell(row, i_eissn))
        impact = _parse_if(_cell(row, i_if))
        kwartyl = _parse_kwartyl(_cell(row, i_kw))
        kategoria = _clean(_cell(row, i_kat))

        key = (issn, e_issn, nazwa)
        cz = grupy.get(key)
        if cz is None:
            cz = CzasopismoJCR(
                nazwa=nazwa,
                issn=issn,
                e_issn=e_issn,
                impact_factor=impact,
                kwartyl_wos=kwartyl,
                kategorie=[],
            )
            grupy[key] = cz
        else:
            if cz.impact_factor is None and impact is not None:
                cz.impact_factor = impact
            if kwartyl is not None and (
                cz.kwartyl_wos is None or kwartyl < cz.kwartyl_wos
            ):
                cz.kwartyl_wos = kwartyl  # najlepszy kwartyl (min)
        cz.kategorie.append((kategoria, kwartyl))

    return ParsedJCR(rok=rok, czasopisma=list(grupy.values()))
```

- [ ] **Step 5: Uruchom — ma PRZEJŚĆ**

Run: `uv run pytest src/import_punktacji_zrodel/tests/test_parser.py -q`
Expected: PASS (wszystkie testy). Jeśli liczność ≠ 136 — sprawdź regułę
footer/`_clean`; jeśli kwartyl błędny — sprawdź `min`.

- [ ] **Step 6: Lint + commit**

```bash
ruff format src/import_punktacji_zrodel/
ruff check src/import_punktacji_zrodel/
git add src/import_punktacji_zrodel/parser.py \
        src/import_punktacji_zrodel/tests/conftest.py \
        src/import_punktacji_zrodel/tests/test_parser.py
git commit -m "feat(import_punktacji_zrodel): parser JCR XLSX/CSV z grupowaniem i best-kwartyl (FD#388)"
```

---

### Task 3: Modele + migracja

**Files:**
- Create: `src/import_punktacji_zrodel/models.py`
- Create: `src/import_punktacji_zrodel/admin.py`
- Test: `src/import_punktacji_zrodel/tests/test_core.py` (tylko 1 test modelu
  na tym etapie — rozszerzymy w Task 4)
- Generated: `src/import_punktacji_zrodel/migrations/0001_initial.py`

**Interfaces:**
- Produces:
  - `ImportPunktacjiZrodel(ASGINotificationMixin, Operation)` z polami:
    `rok (YearField null)`, `plik (FileField)`, `zapisz_zmiany_do_bazy`,
    `importuj_impact_factor`, `importuj_kwartyl_wos`,
    `ignoruj_zrodla_bez_odpowiednika`, `nie_porownuj_po_tytulach`;
    metody `perform()`, `on_reset()`, `get_details_set()`.
  - `WierszImportuPunktacjiZrodel` z polami: `parent (FK)`,
    `dane_z_xls (JSON)`, `nr_wiersza`, `zrodlo (FK SET_NULL)`,
    `rezultat (Text)`, `wymaga_zmian (bool)`, `is_duplicate`,
    `duplicate_of_row`, `duplicate_reason`.

- [ ] **Step 1: Napisz failing test modelu**

Dodaj do `src/import_punktacji_zrodel/tests/test_core.py`:

```python
import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_model_tworzy_sie_i_ma_wiersze(admin_user):
    from import_punktacji_zrodel.models import (
        ImportPunktacjiZrodel,
        WierszImportuPunktacjiZrodel,
    )

    imp = baker.make(ImportPunktacjiZrodel, owner=admin_user, rok=2025)
    WierszImportuPunktacjiZrodel.objects.create(
        parent=imp, dane_z_xls={"nazwa": "X"}, nr_wiersza=1, rezultat="ok"
    )
    assert imp.get_details_set().count() == 1
```

- [ ] **Step 2: Uruchom — ma PAŚĆ**

Run: `uv run pytest src/import_punktacji_zrodel/tests/test_core.py -q`
Expected: FAIL (`ModuleNotFoundError` / brak modelu).

- [ ] **Step 3: Zaimplementuj models.py**

```python
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from bpp.fields import YearField
from bpp.models import Zrodlo
from long_running.models import Operation
from long_running.notification_mixins import ASGINotificationMixin


class ImportPunktacjiZrodel(ASGINotificationMixin, Operation):
    rok = YearField(null=True, blank=True)
    plik = models.FileField(upload_to="protected/import_punktacji_zrodel/")
    zapisz_zmiany_do_bazy = models.BooleanField(
        default=False,
        help_text="Gdy odznaczone — tylko podgląd, bez zapisu do bazy.",
    )
    importuj_impact_factor = models.BooleanField(default=True)
    importuj_kwartyl_wos = models.BooleanField(default=True)
    ignoruj_zrodla_bez_odpowiednika = models.BooleanField(default=False)
    nie_porownuj_po_tytulach = models.BooleanField(
        default=False,
        help_text="Dopasowuj wyłącznie po ISSN/eISSN, pomijając tytuły.",
    )

    class Meta:
        verbose_name = "import punktacji źródeł"
        verbose_name_plural = "importy punktacji źródeł"

    def perform(self):
        from import_punktacji_zrodel.core import analyze_jcr_file

        analyze_jcr_file(self.plik.path, self)

    def on_reset(self):
        self.get_details_set().delete()

    def get_details_set(self):
        return self.wierszimportupunktacjizrodel_set.all().select_related(
            "zrodlo"
        )


class WierszImportuPunktacjiZrodel(models.Model):
    parent = models.ForeignKey(
        ImportPunktacjiZrodel, on_delete=models.CASCADE
    )
    dane_z_xls = models.JSONField(
        null=True, blank=True, encoder=DjangoJSONEncoder
    )
    nr_wiersza = models.PositiveIntegerField()
    zrodlo = models.ForeignKey(
        Zrodlo, on_delete=models.SET_NULL, null=True, blank=True
    )
    rezultat = models.TextField(blank=True, default="")
    wymaga_zmian = models.BooleanField(default=False)

    is_duplicate = models.BooleanField(default=False)
    duplicate_of_row = models.PositiveIntegerField(null=True, blank=True)
    duplicate_reason = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ("nr_wiersza",)
```

- [ ] **Step 4: admin.py (minimalny, spójny z siblingami)**

```python
# Brak rejestracji w adminie — operacje obsługiwane są przez widoki
# frontendowe (long_running). Plik istnieje dla spójności struktury app.
```

- [ ] **Step 5: Wygeneruj migrację**

Run: `uv run python src/manage.py makemigrations import_punktacji_zrodel`
Expected: utworzono `0001_initial.py` (2 modele). NIE edytuj ręcznie.

- [ ] **Step 6: Uruchom test — ma PRZEJŚĆ**

Run: `uv run pytest src/import_punktacji_zrodel/tests/test_core.py -q`
Expected: PASS.

- [ ] **Step 7: makemigrations --check (brak driftu) + commit**

Run: `uv run python src/manage.py makemigrations --check --dry-run 2>&1 | tail -3`
Expected: `No changes detected`.

```bash
ruff format src/import_punktacji_zrodel/
ruff check src/import_punktacji_zrodel/
git add src/import_punktacji_zrodel/models.py \
        src/import_punktacji_zrodel/admin.py \
        src/import_punktacji_zrodel/migrations/0001_initial.py \
        src/import_punktacji_zrodel/tests/test_core.py
git commit -m "feat(import_punktacji_zrodel): modele importu + migracja 0001 (FD#388)"
```

---

### Task 4: Logika importu `core.analyze_jcr_file` (dopasowanie + dry-run/commit)

**Files:**
- Create: `src/import_punktacji_zrodel/core.py`
- Test: `src/import_punktacji_zrodel/tests/test_core.py` (rozszerzenie)

**Interfaces:**
- Consumes: `wczytaj_plik_jcr` (Task 2); modele (Task 3);
  `import_common.core.matchuj_zrodlo`; `bpp.models.Punktacja_Zrodla`.
- Produces: `analyze_jcr_file(path: str, parent: ImportPunktacjiZrodel) ->
  None` — tworzy `WierszImportuPunktacjiZrodel` per czasopismo; zapisuje do
  `Punktacja_Zrodla` tylko gdy `parent.zapisz_zmiany_do_bazy`.

- [ ] **Step 1: Napisz failing testy logiki**

Dodaj do `src/import_punktacji_zrodel/tests/test_core.py`:

```python
from decimal import Decimal

from import_punktacji_zrodel.core import analyze_jcr_file


def _make_import(admin_user, **kw):
    from import_punktacji_zrodel.models import ImportPunktacjiZrodel

    defaults = dict(
        owner=admin_user,
        rok=2025,
        zapisz_zmiany_do_bazy=False,
        importuj_impact_factor=True,
        importuj_kwartyl_wos=True,
        ignoruj_zrodla_bez_odpowiednika=False,
        nie_porownuj_po_tytulach=False,
    )
    defaults.update(kw)
    return baker.make(ImportPunktacjiZrodel, **defaults)


@pytest.mark.django_db
def test_dry_run_nic_nie_zapisuje(admin_user, jcr_xlsx_path):
    from bpp.models import Punktacja_Zrodla, Zrodlo

    zrodlo = baker.make(Zrodlo, nazwa="LANCET", issn="0140-6736")
    imp = _make_import(admin_user, zapisz_zmiany_do_bazy=False)
    analyze_jcr_file(jcr_xlsx_path, imp)

    # dry-run: brak wpisu Punktacja_Zrodla
    assert not Punktacja_Zrodla.objects.filter(
        zrodlo=zrodlo, rok=2025
    ).exists()
    # ale wiersz raportu istnieje i wskazuje zmianę
    wiersz = imp.get_details_set().get(zrodlo=zrodlo)
    assert wiersz.wymaga_zmian is True


@pytest.mark.django_db
def test_commit_zapisuje_if_i_kwartyl(admin_user, jcr_xlsx_path):
    from bpp.models import Punktacja_Zrodla, Zrodlo

    zrodlo = baker.make(Zrodlo, nazwa="LANCET", issn="0140-6736")
    imp = _make_import(admin_user, zapisz_zmiany_do_bazy=True)
    analyze_jcr_file(jcr_xlsx_path, imp)

    pz = Punktacja_Zrodla.objects.get(zrodlo=zrodlo, rok=2025)
    assert pz.impact_factor == Decimal("109.000")
    assert pz.kwartyl_w_wos == 1


@pytest.mark.django_db
def test_bez_zmian_gdy_wartosci_rowne(admin_user, jcr_xlsx_path):
    from bpp.models import Zrodlo

    zrodlo = baker.make(Zrodlo, nazwa="LANCET", issn="0140-6736")
    zrodlo.punktacja_zrodla_set.create(
        rok=2025, impact_factor=Decimal("109.000"), kwartyl_w_wos=1
    )
    imp = _make_import(admin_user, zapisz_zmiany_do_bazy=True)
    analyze_jcr_file(jcr_xlsx_path, imp)

    wiersz = imp.get_details_set().get(zrodlo=zrodlo)
    assert wiersz.wymaga_zmian is False
    assert "bez zmian" in wiersz.rezultat


@pytest.mark.django_db
def test_niedopasowane_zrodlo(admin_user, jcr_xlsx_path):
    # Brak jakichkolwiek Zrodel -> wszystkie wiersze "Brak źródła w BPP"
    imp = _make_import(admin_user, zapisz_zmiany_do_bazy=True)
    analyze_jcr_file(jcr_xlsx_path, imp)
    assert imp.get_details_set().filter(
        rezultat__icontains="Brak źródła"
    ).exists()


@pytest.mark.django_db
def test_toggle_kwartyl_off(admin_user, jcr_xlsx_path):
    from bpp.models import Punktacja_Zrodla, Zrodlo

    zrodlo = baker.make(Zrodlo, nazwa="LANCET", issn="0140-6736")
    imp = _make_import(
        admin_user, zapisz_zmiany_do_bazy=True, importuj_kwartyl_wos=False
    )
    analyze_jcr_file(jcr_xlsx_path, imp)

    pz = Punktacja_Zrodla.objects.get(zrodlo=zrodlo, rok=2025)
    assert pz.impact_factor == Decimal("109.000")
    assert pz.kwartyl_w_wos is None  # nie ruszony


@pytest.mark.django_db
def test_autodetekcja_roku_gdy_brak(admin_user, jcr_xlsx_path):
    imp = _make_import(admin_user, rok=None, zapisz_zmiany_do_bazy=False)
    analyze_jcr_file(jcr_xlsx_path, imp)
    imp.refresh_from_db()
    assert imp.rok == 2025
```

- [ ] **Step 2: Uruchom — ma PAŚĆ**

Run: `uv run pytest src/import_punktacji_zrodel/tests/test_core.py -q`
Expected: FAIL (brak `core.analyze_jcr_file`).

- [ ] **Step 3: Zaimplementuj core.py**

```python
"""Logika importu punktacji źródeł z pliku JCR do Punktacja_Zrodla."""

from django.contrib.messages import constants

from import_common.core import matchuj_zrodlo
from import_punktacji_zrodel.parser import wczytaj_plik_jcr

_KWARTYL_LABEL = {None: "brak", 1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}


def _q(v) -> str:
    return _KWARTYL_LABEL.get(v, str(v))


def _detect_duplicates(czasopisma):
    """Zwraca {index: (index_pierwszego, "ISSN"/"eISSN")} dla powtórzeń."""
    dups = {}
    issn_seen = {}
    eissn_seen = {}
    for i, cz in enumerate(czasopisma):
        powody = []
        first = None
        if cz.issn:
            if cz.issn in issn_seen:
                powody.append("ISSN")
                first = issn_seen[cz.issn]
            else:
                issn_seen[cz.issn] = i
        if cz.e_issn:
            if cz.e_issn in eissn_seen:
                powody.append("eISSN")
                if first is None:
                    first = eissn_seen[cz.e_issn]
            else:
                eissn_seen[cz.e_issn] = i
        if powody:
            dups[i] = (first, ", ".join(powody))
    return dups


def analyze_jcr_file(path, parent):
    parsed = wczytaj_plik_jcr(path)

    rok = parent.rok or parsed.rok
    if rok is None:
        msg = "Nie udało się ustalić roku (brak nagłówka i metadanych JCR)."
        parent.wierszimportupunktacjizrodel_set.create(
            nr_wiersza=0, dane_z_xls={}, rezultat=msg
        )
        parent.send_notification(msg, level=constants.ERROR)
        raise ValueError(msg)
    if parent.rok is None:
        parent.rok = rok
        parent.save(update_fields=["rok"])

    dry_run = not parent.zapisz_zmiany_do_bazy
    dups = _detect_duplicates(parsed.czasopisma)
    total = len(parsed.czasopisma) or 1

    for i, cz in enumerate(parsed.czasopisma):
        parent.send_progress((i + 1) * 100.0 / total)

        is_dup = i in dups
        dup_of, dup_reason = dups.get(i, (None, ""))
        dup_prefix = ""
        if is_dup:
            dup_prefix = f"DUPLIKAT wiersza {dup_of + 1} ({dup_reason}). "

        zrodlo = matchuj_zrodlo(
            cz.nazwa,
            issn=cz.issn,
            e_issn=cz.e_issn,
            disable_fuzzy=True,
            disable_skrot=True,
            disable_title_matching=parent.nie_porownuj_po_tytulach,
        )

        dane = {
            "nazwa": cz.nazwa,
            "issn": cz.issn,
            "e_issn": cz.e_issn,
            "impact_factor": (
                str(cz.impact_factor) if cz.impact_factor is not None else None
            ),
            "kwartyl_wos": cz.kwartyl_wos,
        }

        if zrodlo is None:
            parent.wierszimportupunktacjizrodel_set.create(
                nr_wiersza=i + 1,
                dane_z_xls=dane,
                zrodlo=None,
                rezultat=dup_prefix + "Brak źródła w BPP",
                wymaga_zmian=False,
                is_duplicate=is_dup,
                duplicate_of_row=(dup_of + 1) if dup_of is not None else None,
                duplicate_reason=dup_reason,
            )
            continue

        pz = zrodlo.punktacja_zrodla_set.filter(rok=rok).first()
        operacje = []
        wymaga = False
        to_save = {}

        if parent.importuj_impact_factor:
            if cz.impact_factor is None:
                operacje.append("IF: brak danych (N/A) w pliku")
            else:
                stare = pz.impact_factor if pz else None
                if stare != cz.impact_factor:
                    operacje.append(
                        f"IF: {stare if stare is not None else 'brak'} "
                        f"→ {cz.impact_factor}"
                    )
                    wymaga = True
                    to_save["impact_factor"] = cz.impact_factor
                else:
                    operacje.append("IF bez zmian")

        if parent.importuj_kwartyl_wos:
            if cz.kwartyl_wos is None:
                operacje.append("Kwartyl: brak danych (N/A) w pliku")
            else:
                stare_q = pz.kwartyl_w_wos if pz else None
                if stare_q != cz.kwartyl_wos:
                    operacje.append(
                        f"Kwartyl: {_q(stare_q)} → {_q(cz.kwartyl_wos)}"
                    )
                    wymaga = True
                    to_save["kwartyl_w_wos"] = cz.kwartyl_wos
                else:
                    operacje.append("Kwartyl bez zmian")

        if to_save and not dry_run:
            if pz is None:
                pz = zrodlo.punktacja_zrodla_set.create(rok=rok)
            for k, v in to_save.items():
                setattr(pz, k, v)
            pz.save(update_fields=list(to_save))

        parent.wierszimportupunktacjizrodel_set.create(
            nr_wiersza=i + 1,
            dane_z_xls=dane,
            zrodlo=zrodlo,
            rezultat=dup_prefix + ". ".join(operacje),
            wymaga_zmian=wymaga,
            is_duplicate=is_dup,
            duplicate_of_row=(dup_of + 1) if dup_of is not None else None,
            duplicate_reason=dup_reason,
        )
```

- [ ] **Step 4: Uruchom — ma PRZEJŚĆ**

Run: `uv run pytest src/import_punktacji_zrodel/tests/test_core.py -q`
Expected: PASS (wszystkie).

- [ ] **Step 5: Lint + commit**

```bash
ruff format src/import_punktacji_zrodel/
ruff check src/import_punktacji_zrodel/
git add src/import_punktacji_zrodel/core.py \
        src/import_punktacji_zrodel/tests/test_core.py
git commit -m "feat(import_punktacji_zrodel): logika dopasowania + dry-run/commit IF i kwartyla (FD#388)"
```

---

### Task 5: Formularz, widoki, URL-e (long_running) + ZatwierdzImportView

**Files:**
- Create: `src/import_punktacji_zrodel/forms.py`
- Create: `src/import_punktacji_zrodel/views.py`
- Create: `src/import_punktacji_zrodel/urls.py`
- Modify: `src/django_bpp/urls.py`
- Test: `src/import_punktacji_zrodel/tests/test_views.py`

**Interfaces:**
- Consumes: modele (Task 3); `long_running.views.*`;
  `long_running.views.LongRunningTaskCallerMixin`,
  `long_running.views.RestrictToOwnerMixin`.
- Produces: URL-e `import_punktacji_zrodel:index`, `:new`,
  `:importpunktacjizrodel-router`, `:importpunktacjizrodel-details`,
  `:importpunktacjizrodel-results`, `:restart`, `:zatwierdz`.

- [ ] **Step 1: Napisz failing test widoków (uprawnienia + formularz)**

`src/import_punktacji_zrodel/tests/test_views.py`:

```python
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse


@pytest.mark.django_db
def test_index_wymaga_grupy(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="u1", password="x"
    )
    client.force_login(user)
    resp = client.get(reverse("import_punktacji_zrodel:index"))
    assert resp.status_code in (403, 302)  # brak grupy


@pytest.mark.django_db
def test_index_dostepny_dla_grupy(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="u2", password="x"
    )
    grupa, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    user.groups.add(grupa)
    client.force_login(user)
    resp = client.get(reverse("import_punktacji_zrodel:index"))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_formularz_nowego_importu_get(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="u3", password="x"
    )
    grupa, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    user.groups.add(grupa)
    client.force_login(user)
    resp = client.get(reverse("import_punktacji_zrodel:new"))
    assert resp.status_code == 200
    assert b"plik" in resp.content.lower()
```

- [ ] **Step 2: Uruchom — ma PAŚĆ**

Run: `uv run pytest src/import_punktacji_zrodel/tests/test_views.py -q`
Expected: FAIL (brak urls/views — `NoReverseMatch`).

- [ ] **Step 3: forms.py**

```python
import os

from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Submit
from crispy_forms_foundation.layout import Column, Fieldset, Layout, Row
from django import forms
from django.core.exceptions import ValidationError

from bpp.util import formdefaults_html_after, formdefaults_html_before
from import_punktacji_zrodel.models import ImportPunktacjiZrodel


class NowyImportForm(forms.ModelForm):
    class Meta:
        model = ImportPunktacjiZrodel
        fields = [
            "plik",
            "rok",
            "importuj_impact_factor",
            "importuj_kwartyl_wos",
            "ignoruj_zrodla_bez_odpowiednika",
            "nie_porownuj_po_tytulach",
            "zapisz_zmiany_do_bazy",
        ]

    def clean_plik(self):
        plik = self.cleaned_data.get("plik")
        if plik:
            ext = os.path.splitext(plik.name)[1].lower()
            if ext not in (".xlsx", ".xls", ".csv"):
                raise ValidationError(
                    "Niewłaściwy format pliku. Dozwolone: .xlsx, .xls, .csv "
                    f"(otrzymano: {ext})."
                )
        return plik

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_class = "custom"
        self.helper.form_action = "."
        self.helper.layout = Layout(
            Fieldset(
                "Wybierz parametry importu",
                formdefaults_html_before(self),
                Row(Column("rok", css_class="large-12 small-12")),
                Row(
                    Column(
                        "importuj_impact_factor",
                        css_class="large-12 small-12",
                    )
                ),
                Row(
                    Column(
                        "importuj_kwartyl_wos", css_class="large-12 small-12"
                    )
                ),
                Row(
                    Column(
                        "ignoruj_zrodla_bez_odpowiednika",
                        css_class="large-12 small-12",
                    )
                ),
                Row(
                    Column(
                        "nie_porownuj_po_tytulach",
                        css_class="large-12 small-12",
                    )
                ),
                Row(
                    Column(
                        "zapisz_zmiany_do_bazy",
                        css_class="large-12 small-12",
                    )
                ),
                Row(Column("plik", css_class="large-12 small-12")),
                formdefaults_html_after(self),
            ),
            ButtonHolder(
                Submit(
                    "submit",
                    "Wczytaj i pokaż podgląd",
                    css_id="id_submit",
                    css_class="submit button",
                ),
            ),
        )
        super().__init__(*args, **kwargs)
```

- [ ] **Step 4: views.py**

```python
from braces.views import GroupRequiredMixin
from django.db import transaction
from django.http import HttpResponseRedirect
from django.views.generic import DetailView

from import_punktacji_zrodel.forms import NowyImportForm
from import_punktacji_zrodel.models import ImportPunktacjiZrodel
from long_running.views import (
    CreateLongRunningOperationView,
    LongRunningDetailsView,
    LongRunningOperationsView,
    LongRunningResultsView,
    LongRunningRouterView,
    LongRunningTaskCallerMixin,
    RestartLongRunningOperationView,
    RestrictToOwnerMixin,
)


class BaseMixin(GroupRequiredMixin):
    group_required = "wprowadzanie danych"
    model = ImportPunktacjiZrodel


class ListaImportowView(BaseMixin, LongRunningOperationsView):
    pass


class NowyImportView(BaseMixin, CreateLongRunningOperationView):
    form_class = NowyImportForm


class RouterView(BaseMixin, LongRunningRouterView):
    pass


class DetailsView(BaseMixin, LongRunningDetailsView):
    pass


class ResultsView(BaseMixin, LongRunningResultsView):
    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.GET.get("tylko_do_aktualizacji") == "1":
            qs = qs.filter(wymaga_zmian=True)
        if self.request.GET.get("tylko_niedopasowane") == "1":
            qs = qs.filter(zrodlo__isnull=True)
        if self.request.GET.get("tylko_duplikaty") == "1":
            qs = qs.filter(is_duplicate=True)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        wszystkie = self.parent_object.get_details_set()
        ctx["total_count"] = wszystkie.count()
        ctx["do_aktualizacji_count"] = wszystkie.filter(
            wymaga_zmian=True
        ).count()
        ctx["niedopasowane_count"] = wszystkie.filter(
            zrodlo__isnull=True
        ).count()
        ctx["duplikaty_count"] = wszystkie.filter(is_duplicate=True).count()
        ctx["rok"] = self.parent_object.rok
        ctx["byl_dry_run"] = not self.parent_object.zapisz_zmiany_do_bazy
        return ctx


class RestartImportView(BaseMixin, RestartLongRunningOperationView):
    pass


class ZatwierdzImportView(
    RestrictToOwnerMixin, LongRunningTaskCallerMixin, DetailView
):
    """Przełącza dry-run -> commit i ponownie uruchamia przetwarzanie
    na już zapisanym pliku (bez ponownego uploadu)."""

    model = ImportPunktacjiZrodel
    group_required = "wprowadzanie danych"

    @transaction.atomic
    def post(self, *args, **kwargs):
        self.object = self.get_object()
        self.object.zapisz_zmiany_do_bazy = True
        self.object.save(update_fields=["zapisz_zmiany_do_bazy"])
        self.object.mark_reset()
        self.task_on_commit(pk=self.object.pk)
        return HttpResponseRedirect(self.object.get_url("router"))
```

- [ ] **Step 5: urls.py**

```python
from django.urls import path

from import_punktacji_zrodel.views import (
    DetailsView,
    ListaImportowView,
    NowyImportView,
    ResultsView,
    RestartImportView,
    RouterView,
    ZatwierdzImportView,
)

app_name = "import_punktacji_zrodel"

urlpatterns = [
    path("", ListaImportowView.as_view(), name="index"),
    path("new/", NowyImportView.as_view(), name="new"),
    path(
        "<uuid:pk>/",
        RouterView.as_view(),
        name="importpunktacjizrodel-router",
    ),
    path(
        "<uuid:pk>/detale/",
        DetailsView.as_view(),
        name="importpunktacjizrodel-details",
    ),
    path(
        "<uuid:pk>/rezultaty/",
        ResultsView.as_view(),
        name="importpunktacjizrodel-results",
    ),
    path("<uuid:pk>/regen/", RestartImportView.as_view(), name="restart"),
    path(
        "<uuid:pk>/zatwierdz/",
        ZatwierdzImportView.as_view(),
        name="zatwierdz",
    ),
]
```

- [ ] **Step 6: Podłącz urls w głównym urlconf**

W `src/django_bpp/urls.py`, obok pozostałych `import_*` include'ów dodaj:

```python
        path(
            "import_punktacji_zrodel/",
            include("import_punktacji_zrodel.urls"),
        ),
```

- [ ] **Step 7: Uruchom — ma PRZEJŚĆ (po dodaniu szablonów w Task 6 część
  testów index/new wymaga template — jeśli FAIL na braku template, przejdź
  do Task 6 i wróć)**

Run: `uv run pytest src/import_punktacji_zrodel/tests/test_views.py -q`
Expected: testy uprawnień przechodzą; `test_index/new` mogą wymagać szablonu
z Task 6. Jeśli `TemplateDoesNotExist` — to oczekiwane do Task 6.

- [ ] **Step 8: Lint + commit**

```bash
ruff format src/import_punktacji_zrodel/ src/django_bpp/urls.py
ruff check src/import_punktacji_zrodel/
git add src/import_punktacji_zrodel/forms.py \
        src/import_punktacji_zrodel/views.py \
        src/import_punktacji_zrodel/urls.py \
        src/django_bpp/urls.py \
        src/import_punktacji_zrodel/tests/test_views.py
git commit -m "feat(import_punktacji_zrodel): formularz, widoki long_running, urls + zatwierdz (FD#388)"
```

---

### Task 6: Szablony frontendowe

**Files:**
- Create: `templates/import_punktacji_zrodel/importpunktacjizrodel_form.html`
- Create: `templates/import_punktacji_zrodel/importpunktacjizrodel_list.html`
- Create: `templates/import_punktacji_zrodel/importpunktacjizrodel_detail.html`
- Create: `templates/import_punktacji_zrodel/wierszimportupunktacjizrodel_list.html`

> Szablony szukane są w `src/<app>/templates/...`. Twórz je w
> `src/import_punktacji_zrodel/templates/import_punktacji_zrodel/`.
> Wzór: `src/import_list_ministerialnych/templates/...` — odczytaj te pliki
> i odtwórz strukturę, podmieniając nazwy URL/pola wg poniższego.

**Interfaces:**
- Consumes: konteksty z widoków Task 5 (`object_list`, `object`,
  `total_count`, `do_aktualizacji_count`, `niedopasowane_count`,
  `duplikaty_count`, `rok`, `byl_dry_run`).

- [ ] **Step 1: `importpunktacjizrodel_form.html`**

```django
{% extends "base.html" %}
{% load crispy_forms_tags %}
{% block title %}Import punktacji źródeł — nowy{% endblock %}
{% block content %}
  <h1>Import punktacji źródeł — nowy import</h1>
  <p>Wczytaj plik z bazy Journal Citation Reports (XLSX lub CSV). Zobaczysz
     podgląd rozbieżności; zapis nastąpi dopiero po zatwierdzeniu.</p>
  {% crispy form %}
{% endblock %}
```

- [ ] **Step 2: `importpunktacjizrodel_list.html`**

```django
{% extends "base.html" %}
{% block title %}Import punktacji źródeł{% endblock %}
{% block content %}
  <h1>Import punktacji źródeł</h1>
  <p><a class="button" href="{% url 'import_punktacji_zrodel:new' %}">
     <i class="fi-plus"></i> Nowy import</a></p>
  <table>
    <thead><tr><th>Utworzono</th><th>Rok</th><th>Status</th></tr></thead>
    <tbody>
    {% for op in object_list %}
      <tr>
        <td><a href="{% url 'import_punktacji_zrodel:importpunktacjizrodel-router' op.pk %}">
            {{ op.created_on }}</a></td>
        <td>{{ op.rok|default:"—" }}</td>
        <td>{% if op.finished_successfully %}gotowe
            {% elif op.started_on %}w toku{% else %}oczekuje{% endif %}</td>
      </tr>
    {% empty %}
      <tr><td colspan="3">Brak importów.</td></tr>
    {% endfor %}
    </tbody>
  </table>
{% endblock %}
```

- [ ] **Step 3: `importpunktacjizrodel_detail.html`** (progress — wzór z
  siblinga; reużywa includa long_running)

```django
{% extends "base.html" %}
{% block title %}Import punktacji źródeł — postęp{% endblock %}
{% block content %}
  <h1>Import punktacji źródeł — przetwarzanie</h1>
  {% include "long_running/operation_details.html" %}
{% endblock %}
```

> Jeśli `long_running/operation_details.html` nie istnieje pod tą nazwą —
> odczytaj `src/import_list_ministerialnych/templates/import_list_ministerialnych/
> importlistministerialnych_detail.html` i odtwórz dokładnie ten sam include
> oraz subskrypcję kanału postępu.

- [ ] **Step 4: `wierszimportupunktacjizrodel_list.html`** (raport wyników)

```django
{% extends "base.html" %}
{% block title %}Import punktacji źródeł — wyniki{% endblock %}
{% block content %}
  <h1>Wyniki importu punktacji źródeł{% if rok %} (rok {{ rok }}){% endif %}</h1>

  <div class="callout">
    <ul class="menu">
      <li>Wszystkich: <strong>{{ total_count }}</strong></li>
      <li>Do aktualizacji: <strong>{{ do_aktualizacji_count }}</strong></li>
      <li>Niedopasowanych: <strong>{{ niedopasowane_count }}</strong></li>
      <li>Duplikatów: <strong>{{ duplikaty_count }}</strong></li>
    </ul>
  </div>

  {% if byl_dry_run %}
    <div class="callout warning">
      <p>To był <strong>podgląd</strong> — nic nie zapisano do bazy.</p>
      <form method="post"
            action="{% url 'import_punktacji_zrodel:zatwierdz' object.pk %}">
        {% csrf_token %}
        <button type="submit" class="button alert">
          Zatwierdź i zapisz do bazy</button>
      </form>
    </div>
  {% else %}
    <div class="callout success">
      <p>Zmiany zapisane. Aby przenieść wartości na prace (publikacje):</p>
      <ul class="menu">
        <li><a class="button" href="{% url 'rozbieznosci:index' metryka='if' %}?rok_od={{ rok }}&rok_do={{ rok }}">
            rozbieżności punktacji (IF) za {{ rok }}</a></li>
        <li><a class="button" href="{% url 'rozbieznosci:index' metryka='kw_wos' %}?rok_od={{ rok }}&rok_do={{ rok }}">
            rozbieżności kwartyla za {{ rok }}</a></li>
      </ul>
    </div>
  {% endif %}

  <form method="get" class="callout">
    <label><input type="checkbox" name="tylko_do_aktualizacji" value="1"
      {% if request.GET.tylko_do_aktualizacji %}checked{% endif %}>
      tylko do aktualizacji</label>
    <label><input type="checkbox" name="tylko_niedopasowane" value="1"
      {% if request.GET.tylko_niedopasowane %}checked{% endif %}>
      tylko niedopasowane</label>
    <label><input type="checkbox" name="tylko_duplikaty" value="1"
      {% if request.GET.tylko_duplikaty %}checked{% endif %}>
      tylko duplikaty</label>
    <button type="submit" class="button">Filtruj</button>
  </form>

  <table>
    <thead><tr>
      <th>#</th><th>Czasopismo (plik)</th><th>Źródło w BPP</th>
      <th>Rezultat</th>
    </tr></thead>
    <tbody>
    {% for w in object_list %}
      <tr {% if w.is_duplicate %}class="warning"{% endif %}>
        <td>{{ w.nr_wiersza }}</td>
        <td>{{ w.dane_z_xls.nazwa }}<br>
            <small>{{ w.dane_z_xls.issn|default:"" }}
                   {{ w.dane_z_xls.e_issn|default:"" }}</small></td>
        <td>{% if w.zrodlo %}{{ w.zrodlo.nazwa }}{% else %}—{% endif %}</td>
        <td>{{ w.rezultat }}</td>
      </tr>
    {% empty %}
      <tr><td colspan="4">Brak wierszy.</td></tr>
    {% endfor %}
    </tbody>
  </table>

  {% if is_paginated %}
    <p>
      {% if page_obj.has_previous %}
        <a href="?page={{ page_obj.previous_page_number }}">« poprzednia</a>
      {% endif %}
      strona {{ page_obj.number }} z {{ page_obj.paginator.num_pages }}
      {% if page_obj.has_next %}
        <a href="?page={{ page_obj.next_page_number }}">następna »</a>
      {% endif %}
    </p>
  {% endif %}
{% endblock %}
```

- [ ] **Step 5: Uruchom testy widoków — mają PRZEJŚĆ**

Run: `uv run pytest src/import_punktacji_zrodel/tests/test_views.py -q`
Expected: PASS (index/new renderują się).

- [ ] **Step 6: Commit**

```bash
git add src/import_punktacji_zrodel/templates/
git commit -m "feat(import_punktacji_zrodel): szablony formularza, listy i raportu (FD#388)"
```

---

### Task 7: Integracja menu (top_bar.html)

**Files:**
- Modify: `src/django_bpp/templates/top_bar.html`

**Interfaces:**
- Consumes: URL `import_punktacji_zrodel:index`; istniejący
  `bpp:xlsx-issn-chunks`.

- [ ] **Step 1: Usuń „eksport ISSNów" z LEWEJ kolumny (wraz z sierocym hr)**

W `src/django_bpp/templates/top_bar.html` w lewej kolumnie (`menu vertical
column-1`) usuń linie (ok. L192–193):

```django
                                    <hr/>
                                    <li><a href="{% url "bpp:xlsx-issn-chunks" %}"><i class="fi-download"></i> eksport ISSNów</a></li>
```

- [ ] **Step 2: Dodaj separator + przeniesiony „eksport ISSNów" + nowy wpis
  w PRAWEJ kolumnie**

W prawej kolumnie (`menu vertical column-2`), po pozycji „deduplikator
źródeł" (ok. L206–207), przed `</ul>`, dodaj:

```django
                                    <hr>
                                    <li><a href="{% url "bpp:xlsx-issn-chunks" %}"><i class="fi-download"></i> eksport ISSNów</a></li>
                                    <li><a href="{% url "import_punktacji_zrodel:index" %}"><i class="fi-graph-bar"></i> import punktacji źródeł</a></li>
```

- [ ] **Step 3: Sprawdź, że szablon się renderuje (check + reverse)**

Run: `uv run python src/manage.py check 2>&1 | tail -3`
Expected: brak błędów.
Run: `uv run python -c "import django; django.setup(); from django.urls import reverse; print(reverse('import_punktacji_zrodel:index'))"`
(z `DJANGO_SETTINGS_MODULE` jak w repo) — Expected: ścieżka
`/import_punktacji_zrodel/`. (Alternatywnie: szybki test klienta na stronie
głównej dla zalogowanego usera z grupą — opcjonalnie.)

- [ ] **Step 4: Commit**

```bash
git add src/django_bpp/templates/top_bar.html
git commit -m "feat(import_punktacji_zrodel): wpis w menu (prawa kolumna) + przenosi eksport ISSNów (FD#388)"
```

---

### Task 8: Test repro FD#388 (pełny przebieg) + newsfragment + finalizacja

**Files:**
- Test: `src/import_punktacji_zrodel/tests/test_repro_fd388.py`
- Create: `src/bpp/newsfragments/+fd388.feature.rst`

**Interfaces:**
- Consumes: cała aplikacja.

- [ ] **Step 1: Napisz test repro (pełny plik → raport → commit)**

`src/import_punktacji_zrodel/tests/test_repro_fd388.py`:

```python
from decimal import Decimal

import pytest
from model_bakery import baker

from import_punktacji_zrodel.core import analyze_jcr_file


@pytest.mark.django_db
def test_repro_fd388_pelny_przebieg(admin_user, jcr_xlsx_path):
    from bpp.models import Punktacja_Zrodla, Zrodlo
    from import_punktacji_zrodel.models import ImportPunktacjiZrodel

    # dwa realne źródła z pliku
    lancet = baker.make(Zrodlo, nazwa="LANCET", issn="0140-6736")
    blood = baker.make(Zrodlo, nazwa="BLOOD", issn="0006-4971")

    imp = baker.make(
        ImportPunktacjiZrodel,
        owner=admin_user,
        rok=2025,
        zapisz_zmiany_do_bazy=True,
        importuj_impact_factor=True,
        importuj_kwartyl_wos=True,
        ignoruj_zrodla_bez_odpowiednika=False,
        nie_porownuj_po_tytulach=False,
    )
    analyze_jcr_file(jcr_xlsx_path, imp)

    # raport pokrywa cały plik (136 czasopism)
    assert imp.get_details_set().count() == 136
    # dopasowane źródła dostały wartości
    pz_lancet = Punktacja_Zrodla.objects.get(zrodlo=lancet, rok=2025)
    assert pz_lancet.impact_factor == Decimal("109.000")
    assert pz_lancet.kwartyl_w_wos == 1
    pz_blood = Punktacja_Zrodla.objects.get(zrodlo=blood, rok=2025)
    assert pz_blood.impact_factor == Decimal("23.900")
    # są też niedopasowane (większość pliku nie ma odpowiednika)
    assert imp.get_details_set().filter(zrodlo__isnull=True).exists()
```

- [ ] **Step 2: Uruchom — ma PRZEJŚĆ**

Run: `uv run pytest src/import_punktacji_zrodel/tests/test_repro_fd388.py -q`
Expected: PASS. (Jeśli `BLOOD` IF≠23.900 — sprawdź wartość w pliku przez
`grep '^"BLOOD"' src/import_punktacji_zrodel/tests/testdata/jcr_fd388.csv`
i popraw asercję do realnej wartości.)

- [ ] **Step 3: Newsfragment**

`src/bpp/newsfragments/+fd388.feature.rst`:

```rst
Dodano import punktacji źródeł z pliku Journal Citation Reports (XLSX/CSV):
po wczytaniu pliku system pokazuje podgląd rozbieżności wskaźnika IF i
kwartyla dla źródeł, a po zatwierdzeniu zapisuje wartości. Przeniesienie na
prace odbywa się przez moduł rozbieżności punktacji (FD#388).
```

- [ ] **Step 4: Pełny zestaw testów aplikacji + lint**

Run: `uv run pytest src/import_punktacji_zrodel/ -q`
Expected: wszystko PASS.

```bash
ruff format src/import_punktacji_zrodel/
ruff check src/import_punktacji_zrodel/
uv run python src/manage.py makemigrations --check --dry-run 2>&1 | tail -3
```
Expected: `No changes detected`.

- [ ] **Step 5: pre-commit (bez argumentów; fix per-issue ręcznie)**

Run: `pre-commit run --files $(git diff --cached --name-only) 2>&1 | tail -20`
(lub `pre-commit` jak w repo). Problemy fiksuj ręcznie Editem, NIE `--fix`.

- [ ] **Step 6: Commit**

```bash
git add src/import_punktacji_zrodel/tests/test_repro_fd388.py \
        src/bpp/newsfragments/+fd388.feature.rst
git commit -m "test+docs(import_punktacji_zrodel): repro FD#388 + newsfragment (FD#388)"
```

---

### Task 9: PR + ślad w Freshdesku

**Files:** brak (operacje git/PR).

- [ ] **Step 1: Push gałęzi**

```bash
git push -u origin fix-fd388-import-punktacji-zrodel
```

- [ ] **Step 2: Utwórz PR**

```bash
gh pr create --repo iplweb/bpp --base dev \
  --head fix-fd388-import-punktacji-zrodel \
  --title "feat(import_punktacji_zrodel): import punktacji źródeł z JCR (Fixes Freshdesk FD#388)" \
  --body "$(cat <<'EOF'
Implementuje import punktacji źródeł z pliku Journal Citation Reports
(XLSX/CSV) do `Punktacja_Zrodla` (Impact Factor + kwartyl Web of Science),
z podglądem rozbieżności i zatwierdzeniem. Poziom prac reużywa istniejący
moduł `rozbieznosci`.

Fixes Freshdesk FD#388 — https://iplweb.freshdesk.com/a/tickets/388

Spec: docs/superpowers/specs/2026-06-30-import-punktacji-zrodel-design.md
Plan: docs/superpowers/plans/2026-06-30-import-punktacji-zrodel.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Prywatna notatka FD#388 (ślad forward) — patrz Krok 2b.6
  skilla ticket-resolver** (private note z lokalizacją gałęzi + linkiem PR;
  bez bramki, wewnętrzna).

- [ ] **Step 4: Pokaż użytkownikowi:** link PR, nazwę gałęzi/worktree,
  podsumowanie diffu, wynik testów. STOP (merge = decyzja użytkownika).

---

## Self-Review (wykonane przy pisaniu planu)

**Spec coverage:** §1 cel → Task 4/8; §2 format → Task 2; §3 parser → Task 2;
§4 model+migracja → Task 3; §5 logika → Task 4; §6 widoki/forms/urls/szablony
→ Task 5/6; §7 podgląd→commit → Task 5 (ZatwierdzImportView) + Task 6 (przycisk
+ linki rozbieznosci); §8 integracja (apps/pyproject/urls/menu/migracja/
newsfragment) → Task 1/5/7/8; §9 testy → Task 2/4/5/8; §10 YAGNI granice →
respektowane (brak logiki prac, brak tworzenia Zrodel, baseline nietknięty);
§11/§12a otwarte/ryzyka → uwzględnione (ISSN z myślnikiem w fixturach i
testach matchowania; eLife test).

**Placeholder scan:** brak TODO/TBD; każdy krok kodowy ma realny kod.
Jedyne „odczytaj sibling" dot. szablonu progres-bar (Task 6 Step 3) — wskazuje
konkretny istniejący plik do odtworzenia 1:1 (nie placeholder logiki).

**Type consistency:** `wczytaj_plik_jcr -> ParsedJCR(rok, czasopisma)`;
`CzasopismoJCR.impact_factor: Decimal|None`, `.kwartyl_wos: int|None` — używane
spójnie w core.py; `analyze_jcr_file(path, parent)` — sygnatura zgodna z
`models.perform()`; nazwy URL `importpunktacjizrodel-{router,details,results}`
zgodne z kontraktem `Operation.get_url`.
