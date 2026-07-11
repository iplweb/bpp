# Import patentów z SQLite (`import_sqlite`) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aplikacja Django `src/import_sqlite/` importująca patenty z pliku SQLite (format harvestera) do modeli `Patent`/`Patent_Autor`, z dopasowaniem autorów przez `Komparator` i ręcznym uzgadnianiem przez CSV.

**Architecture:** Dwie fazy sterowane management-commandami. `scan` czyta sqlite, auto-matchuje distinct-nazwiska (reużywając `crossref_bpp.Komparator`) i wypluwa dwa CSV-e do przeglądu. Człowiek wypełnia kolumnę `decyzja`. `apply` wczytuje decyzje i tworzy/aktualizuje `Patent`-y (idempotentnie po `numer_prawa_wylacznego`) w jednej transakcji z per-patentowymi savepointami. Logika czysta (parsowanie, split nazwisk, IO CSV) odseparowana od ORM.

**Tech Stack:** Django, pytest + `@pytest.mark.django_db`, `model_bakery`, sqlite3 (stdlib), csv (stdlib), reużycie `crossref_bpp.core.Komparator`, `bpp.models.{Patent,Patent_Autor,Autor,Uczelnia,Status_Korekty,Zrodlo_Informacji}`, `denorm.denorms.flush`.

## Global Constraints

- Python `uv run` prefix do WSZYSTKICH komend Pythona. Nigdy goły `python`/`pytest`.
- Max długość linii: 88 znaków (ruff).
- Testy: pytest, funkcje `test_*` bez klas, `@pytest.mark.django_db` dla DB, `model_bakery.baker.make`.
- NIE modyfikować istniejących migracji. Ta apka nie ma modeli → bez migracji.
- Spec źródłowy: `docs/superpowers/specs/2026-07-11-import-sqlite-patenty-design.md`.
- Klucz idempotencji: `numer_prawa_wylacznego` (źródło `all_fields["Numer patentu/prawa"]`).
- `rok` NOT NULL: rok z `application_date`, fallback rok z `Data udzielenia prawa`.
- `afiliuje = bool(jednostka.skupia_pracownikow)`.
- Daty źródłowe w formacie `DD-MM-YYYY`.

---

### Task 1: Scaffold aplikacji + rejestracja

**Files:**
- Create: `src/import_sqlite/__init__.py` (pusty)
- Create: `src/import_sqlite/apps.py`
- Create: `src/import_sqlite/management/__init__.py` (pusty)
- Create: `src/import_sqlite/management/commands/__init__.py` (pusty)
- Create: `src/import_sqlite/core/__init__.py` (pusty)
- Create: `src/import_sqlite/handlers/__init__.py` (pusty)
- Create: `src/import_sqlite/tests/__init__.py` (pusty)
- Modify: `src/django_bpp/settings/base.py` (dodać `"import_sqlite"` do `INSTALLED_APPS`)
- Modify: `pyproject.toml` (dodać `"import_sqlite"` do `[tool.setuptools.packages.find].include`)

**Interfaces:**
- Produces: aplikacja Django `import_sqlite` zarejestrowana; `manage.py check` przechodzi.

- [ ] **Step 1: Utwórz `apps.py`**

```python
from django.apps import AppConfig


class ImportSqliteConfig(AppConfig):
    name = "import_sqlite"
    verbose_name = "Import z plików SQLite (harvestery)"
    default_auto_field = "django.db.models.BigAutoField"
```

- [ ] **Step 2: Utwórz puste `__init__.py`** w `import_sqlite/`, `management/`, `management/commands/`, `core/`, `handlers/`, `tests/`.

- [ ] **Step 3: Zarejestruj w `INSTALLED_APPS`**

W `src/django_bpp/settings/base.py` znajdź listę `INSTALLED_APPS` i dodaj `"import_sqlite",` w sekcji lokalnych aplikacji BPP (obok innych `import_*`).

- [ ] **Step 4: Dodaj do `pyproject.toml`**

W `[tool.setuptools.packages.find].include` dodaj `"import_sqlite",` (zachowaj porządek alfabetyczny listy).

- [ ] **Step 5: Zweryfikuj rejestrację**

Run: `cd ~/Programowanie/bpp-import-sqlite && uv run python src/manage.py check`
Expected: `System check identified no issues` (bez błędów o nieznanej aplikacji).

- [ ] **Step 6: Commit**

```bash
git add src/import_sqlite pyproject.toml src/django_bpp/settings/base.py
git commit -m "feat(import_sqlite): scaffold aplikacji + rejestracja w INSTALLED_APPS"
```

---

### Task 2: Split i normalizacja nazwisk (czyste)

**Files:**
- Create: `src/import_sqlite/core/author_names.py`
- Test: `src/import_sqlite/tests/test_author_names.py`

**Interfaces:**
- Produces:
  - `split_name(s: str) -> tuple[str, str]` → `(given, family)`. Pierwszy token = given, reszta = family. Puste/whitespace → `("", "")`.
  - `sort_key(family: str) -> str` → znormalizowany klucz sortowania (lower, bez diakrytyków, bez znaków niealfanumerycznych) — sąsiadowanie wariantów pisowni.

- [ ] **Step 1: Napisz failing test**

```python
from import_sqlite.core.author_names import sort_key, split_name


def test_split_name_basic():
    assert split_name("Anna Wawruszak") == ("Anna", "Wawruszak")


def test_split_name_hyphenated_surname():
    assert split_name("Wirginia Kukuła-Koch") == ("Wirginia", "Kukuła-Koch")


def test_split_name_multi_token_surname():
    assert split_name("Jan von Neumann") == ("Jan", "von Neumann")


def test_split_name_single_token():
    assert split_name("Cher") == ("", "Cher")


def test_split_name_empty():
    assert split_name("   ") == ("", "")


def test_sort_key_groups_spelling_variants():
    # "Kowalski" i "Kovalski" NIE są równe, ale mają sąsiadujące klucze
    assert sort_key("Kowalski") != sort_key("Kovalski")
    assert abs(ord(sort_key("Kowalski")[2]) - ord(sort_key("Kovalski")[2])) <= 3


def test_sort_key_strips_diacritics_and_case():
    assert sort_key("Kukuła-Koch") == sort_key("kukula koch")
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/import_sqlite/tests/test_author_names.py -q`
Expected: FAIL (ModuleNotFoundError: import_sqlite.core.author_names).

- [ ] **Step 3: Implementacja**

```python
"""Split i normalizacja stringów nazwisk twórców z pola ``inventors``.

Czyste funkcje — bez ORM, bez bazy. Testowalne w izolacji.
"""

import unicodedata


def split_name(s: str) -> tuple[str, str]:
    """Rozbij ``"Imię Nazwisko"`` na ``(given, family)``.

    Konwencja źródła (ASB): imię-najpierw. Pierwszy token to imię, cała
    reszta to nazwisko (obsługuje nazwiska wieloczłonowe i łącznikowe).
    Jeden token → traktujemy jako samo nazwisko. Puste → ``("", "")``.
    """
    tokens = (s or "").split()
    if not tokens:
        return ("", "")
    if len(tokens) == 1:
        return ("", tokens[0])
    return (tokens[0], " ".join(tokens[1:]))


def sort_key(family: str) -> str:
    """Klucz sortowania: lower, bez diakrytyków, bez znaków spoza [a-z0-9 ].

    Warianty pisowni tego samego nazwiska lądują blisko siebie w sortowaniu,
    więc człowiek widzi rozjazd (Kowalski/Kovalski) obok siebie w CSV.
    """
    text = unicodedata.normalize("NFKD", family or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    return "".join(c if c.isalnum() or c == " " else " " for c in text).strip()
```

- [ ] **Step 4: Uruchom — ma PASS**

Run: `uv run pytest src/import_sqlite/tests/test_author_names.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/import_sqlite/core/author_names.py src/import_sqlite/tests/test_author_names.py
git commit -m "feat(import_sqlite): split i normalizacja nazwisk twórców"
```

---

### Task 3: Czytnik tabeli `records` z SQLite

**Files:**
- Create: `src/import_sqlite/reader.py`
- Test: `src/import_sqlite/tests/test_reader.py`

**Interfaces:**
- Produces:
  - `@dataclass RawRecord`: `source_id: str`, `source_url: str`, `parsed: dict`.
  - `iter_records(sqlite_path: str, typ: str) -> Iterator[RawRecord]` — czyta tabelę `records` filtrując po `type=typ`, parsuje `parsed_json`. Rekordy z pustym/niepoprawnym `parsed_json` są POMIJANE (z ostrzeżeniem przez `warnings.warn`), nie wywalają iteracji.

- [ ] **Step 1: Napisz failing test**

```python
import json
import sqlite3

import pytest

from import_sqlite.reader import RawRecord, iter_records


def _make_db(tmp_path, rows):
    db = tmp_path / "ppm.sqlite3"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE records (type TEXT, source_id TEXT, source_url TEXT, "
        "raw_html TEXT, content_hash TEXT, fetched_at TEXT, parsed_json TEXT, "
        "parsed_at TEXT)"
    )
    for r in rows:
        con.execute(
            "INSERT INTO records (type, source_id, source_url, parsed_json) "
            "VALUES (?, ?, ?, ?)",
            r,
        )
    con.commit()
    con.close()
    return str(db)


def test_iter_records_yields_parsed(tmp_path):
    db = _make_db(
        tmp_path,
        [
            ("patent", "UML1", "http://x/1", json.dumps({"title": "A"})),
            ("patent", "UML2", "http://x/2", json.dumps({"title": "B"})),
        ],
    )
    out = list(iter_records(db, "patent"))
    assert out == [
        RawRecord("UML1", "http://x/1", {"title": "A"}),
        RawRecord("UML2", "http://x/2", {"title": "B"}),
    ]


def test_iter_records_filters_by_type(tmp_path):
    db = _make_db(
        tmp_path,
        [
            ("patent", "UML1", "http://x/1", json.dumps({"title": "A"})),
            ("project", "UML2", "http://x/2", json.dumps({"title": "B"})),
        ],
    )
    out = list(iter_records(db, "patent"))
    assert [r.source_id for r in out] == ["UML1"]


def test_iter_records_skips_bad_json(tmp_path):
    db = _make_db(
        tmp_path,
        [
            ("patent", "UML1", "http://x/1", "{not json"),
            ("patent", "UML2", "http://x/2", json.dumps({"title": "B"})),
        ],
    )
    with pytest.warns(UserWarning):
        out = list(iter_records(db, "patent"))
    assert [r.source_id for r in out] == ["UML2"]
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/import_sqlite/tests/test_reader.py -q`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implementacja**

```python
"""Generyczny czytnik tabeli ``records`` z bazy harvestera.

Niezależny od typu rekordu — filtruje po kolumnie ``type``. Konkretne
mapowanie ``parsed`` → model BPP robią handlery (``handlers/``).
"""

import json
import sqlite3
import warnings
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class RawRecord:
    source_id: str
    source_url: str
    parsed: dict


def iter_records(sqlite_path: str, typ: str) -> Iterator[RawRecord]:
    """Iteruj rekordy danego ``typ`` z tabeli ``records``.

    Rekordy z pustym/niepoprawnym ``parsed_json`` są pomijane z ostrzeżeniem
    (nie przerywają importu). Kolejność: jak w bazie (bez ORDER BY).
    """
    con = sqlite3.connect(sqlite_path)
    try:
        cur = con.execute(
            "SELECT source_id, source_url, parsed_json FROM records "
            "WHERE type = ?",
            (typ,),
        )
        for source_id, source_url, parsed_json in cur:
            if not parsed_json:
                warnings.warn(f"Pusty parsed_json dla {source_id}", stacklevel=2)
                continue
            try:
                parsed = json.loads(parsed_json)
            except json.JSONDecodeError:
                warnings.warn(
                    f"Niepoprawny parsed_json dla {source_id}", stacklevel=2
                )
                continue
            yield RawRecord(source_id or "", source_url or "", parsed)
    finally:
        con.close()
```

- [ ] **Step 4: Uruchom — ma PASS**

Run: `uv run pytest src/import_sqlite/tests/test_reader.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/import_sqlite/reader.py src/import_sqlite/tests/test_reader.py
git commit -m "feat(import_sqlite): generyczny czytnik tabeli records z sqlite"
```

---

### Task 4: Parsowanie patentu (czyste) — `parsed` → `PatentData`

**Files:**
- Create: `src/import_sqlite/handlers/patent.py`
- Test: `src/import_sqlite/tests/test_patent_parse.py`

**Interfaces:**
- Consumes: `RawRecord` (Task 3).
- Produces:
  - `@dataclass PatentData`: `source_id: str`, `source_url: str`, `tytul: str`, `rok: int | None`, `numer_zgloszenia: str`, `data_zgloszenia: date | None`, `numer_prawa: str`, `data_decyzji: date | None`, `szczegoly: str`, `adnotacje: str`, `inventors: list[str]`.
  - `parse_patent(rec: RawRecord) -> PatentData` — czyste mapowanie (bez ORM). `rok` = rok z `application_date`; fallback rok z `Data udzielenia prawa`; gdy oba brak → `None` (handler DB wtedy wstrzyma). `szczegoly` przycięte do 512, nadmiar → `adnotacje`.
  - `parse_ddmmyyyy(s: str) -> date | None`.

- [ ] **Step 1: Napisz failing test**

```python
from datetime import date

from import_sqlite.handlers.patent import PatentData, parse_ddmmyyyy, parse_patent
from import_sqlite.reader import RawRecord


def _rec(**parsed):
    return RawRecord("UML1", "http://x/1", parsed)


def test_parse_ddmmyyyy_ok():
    assert parse_ddmmyyyy("28-06-2023") == date(2023, 6, 28)


def test_parse_ddmmyyyy_empty():
    assert parse_ddmmyyyy("") is None
    assert parse_ddmmyyyy(None) is None
    assert parse_ddmmyyyy("garbage") is None


def test_parse_patent_basic_fields():
    pd = parse_patent(
        _rec(
            title="Zastosowanie X",
            inventors=["Anna Wawruszak", "Andrzej Stepulak"],
            application_number="P.445383",
            application_date="28-06-2023",
            all_fields={
                "Numer patentu/prawa": "Pat.247645",
                "Data udzielenia prawa": "19-05-2025",
            },
        )
    )
    assert pd.tytul == "Zastosowanie X"
    assert pd.rok == 2023
    assert pd.numer_zgloszenia == "P.445383"
    assert pd.data_zgloszenia == date(2023, 6, 28)
    assert pd.numer_prawa == "Pat.247645"
    assert pd.data_decyzji == date(2025, 5, 19)
    assert pd.inventors == ["Anna Wawruszak", "Andrzej Stepulak"]


def test_parse_patent_rok_fallback_to_grant_year():
    pd = parse_patent(
        _rec(
            title="Bez daty zgłoszenia",
            inventors=["Anna Wawruszak"],
            application_number="",
            application_date="",
            all_fields={
                "Numer patentu/prawa": "Pat.100",
                "Data udzielenia prawa": "19-05-2025",
            },
        )
    )
    assert pd.rok == 2025


def test_parse_patent_szczegoly_truncated_overflow_to_adnotacje():
    pd = parse_patent(
        _rec(
            title="T",
            inventors=["A B"],
            all_fields={
                "Numer patentu/prawa": "Pat.1",
                "Nazwa wynalazku / wzoru / utworu w języku angielskim": "X" * 600,
            },
        )
    )
    assert len(pd.szczegoly) <= 512
    assert "X" * 600 in pd.adnotacje  # nadmiar wylądował w adnotacjach
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/import_sqlite/tests/test_patent_parse.py -q`
Expected: FAIL (ImportError: parse_patent).

- [ ] **Step 3: Implementacja (część czysta — parse)**

```python
"""Handler typu ``patent``: parsowanie ``parsed_json`` → ``PatentData``
(czyste) oraz materializacja ``PatentData`` → modele BPP (DB, Task 7).
"""

from dataclasses import dataclass, field
from datetime import date, datetime

from import_sqlite.reader import RawRecord

SZCZEGOLY_MAX = 512


@dataclass
class PatentData:
    source_id: str
    source_url: str
    tytul: str
    rok: int | None
    numer_zgloszenia: str
    data_zgloszenia: date | None
    numer_prawa: str
    data_decyzji: date | None
    szczegoly: str
    adnotacje: str
    inventors: list[str] = field(default_factory=list)


def parse_ddmmyyyy(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%d-%m-%Y").date()
    except (ValueError, AttributeError):
        return None


def _year_from(s: str | None) -> int | None:
    d = parse_ddmmyyyy(s)
    return d.year if d else None


def parse_patent(rec: RawRecord) -> PatentData:
    p = rec.parsed
    af = p.get("all_fields") or {}

    data_zgloszenia = parse_ddmmyyyy(p.get("application_date"))
    data_decyzji = parse_ddmmyyyy(af.get("Data udzielenia prawa"))
    rok = _year_from(p.get("application_date")) or _year_from(
        af.get("Data udzielenia prawa")
    )

    tytul_ang = af.get("Nazwa wynalazku / wzoru / utworu w języku angielskim") or ""
    mkp = af.get("Klasyfikacja MKP") or ""
    score = p.get("patent_score") or ""
    szczegoly_parts = [x for x in (tytul_ang, mkp, f"Punktacja: {score}" if score else "") if x]
    szczegoly_full = " | ".join(szczegoly_parts)
    szczegoly = szczegoly_full[:SZCZEGOLY_MAX]

    adnotacje_parts = []
    if len(szczegoly_full) > SZCZEGOLY_MAX:
        adnotacje_parts.append(szczegoly_full)
    for key in ("Opis w języku polskim", "Opis w języku angielskim"):
        if af.get(key):
            adnotacje_parts.append(f"{key}: {af[key]}")
    adnotacje = "\n\n".join(adnotacje_parts)

    return PatentData(
        source_id=rec.source_id,
        source_url=rec.source_url,
        tytul=(p.get("title") or "").strip(),
        rok=rok,
        numer_zgloszenia=(p.get("application_number") or "").strip(),
        data_zgloszenia=data_zgloszenia,
        numer_prawa=(af.get("Numer patentu/prawa") or "").strip(),
        data_decyzji=data_decyzji,
        szczegoly=szczegoly,
        adnotacje=adnotacje,
        inventors=list(p.get("inventors") or []),
    )
```

- [ ] **Step 4: Uruchom — ma PASS**

Run: `uv run pytest src/import_sqlite/tests/test_patent_parse.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/import_sqlite/handlers/patent.py src/import_sqlite/tests/test_patent_parse.py
git commit -m "feat(import_sqlite): parsowanie parsed_json patentu -> PatentData"
```

---

### Task 5: Dopasowanie autorów — wrapper na Komparator + agregacja distinct

**Files:**
- Create: `src/import_sqlite/core/author_matching.py`
- Test: `src/import_sqlite/tests/test_author_matching.py`
- Create/append fixtures: `src/import_sqlite/tests/conftest.py`

**Interfaces:**
- Consumes: `split_name` (Task 2).
- Produces:
  - `@dataclass Candidate`: `pk: int`, `label: str` (`"Nazwisko Imię"`), `pewnosc: float`, `publikacji: int`.
  - `@dataclass DistinctAuthor`: `nazwisko_zrodlowe: str`, `given: str`, `family: str`, `wystapien: int`, `status: str` (`DOKLADNE`/`LUZNE`/`WYMAGA_INGERENCJI`/`BRAK`), `candidates: list[Candidate]` (max 3), `prefill_pk: int | None`.
  - `match_name(nazwisko_zrodlowe: str) -> DistinctAuthor` (bez `wystapien` — ustawiane przez agregator; tu `wystapien=0`). Woła `Komparator.porownaj_author`. Status `BLAD`/brak kandydatów → `"BRAK"`. `prefill_pk` ustawiony TYLKO gdy status `DOKLADNE`.
  - `aggregate_distinct(name_strings: list[str]) -> list[DistinctAuthor]` — zlicza wystąpienia, matchuje każdy distinct RAZ, sortuje po `sort_key(family)`.

- [ ] **Step 1: conftest — wspólne fixtures słownikowe**

```python
import pytest
from model_bakery import baker


@pytest.fixture
def typ_odpowiedzialnosci_aut(db):
    return baker.make("bpp.Typ_Odpowiedzialnosci", skrot="aut.", nazwa="autor")


@pytest.fixture
def charakter_pat(db):
    return baker.make("bpp.Charakter_Formalny", skrot="PAT", nazwa="Patent")


@pytest.fixture
def jezyk_polski(db):
    return baker.make("bpp.Jezyk", nazwa="polski", skrot="pol.")


@pytest.fixture
def status_korekty(db):
    return baker.make("bpp.Status_Korekty", nazwa="przed korektą")
```

- [ ] **Step 2: Napisz failing test**

```python
import pytest
from model_bakery import baker

from import_sqlite.core.author_matching import aggregate_distinct, match_name


@pytest.mark.django_db
def test_match_name_exact_prefill():
    a = baker.make("bpp.Autor", nazwisko="Wawruszak", imiona="Anna")
    da = match_name("Anna Wawruszak")
    assert da.status == "DOKLADNE"
    assert da.prefill_pk == a.pk
    assert da.candidates and da.candidates[0].pk == a.pk


@pytest.mark.django_db
def test_match_name_no_match_is_brak():
    da = match_name("Zdzisław Niedopasowany")
    assert da.status == "BRAK"
    assert da.candidates == []
    assert da.prefill_pk is None


@pytest.mark.django_db
def test_aggregate_distinct_counts_and_sorts():
    baker.make("bpp.Autor", nazwisko="Wawruszak", imiona="Anna")
    names = ["Anna Wawruszak", "Anna Wawruszak", "Zzz Ostatni", "Aaa Pierwszy"]
    out = aggregate_distinct(names)
    by_name = {d.nazwisko_zrodlowe: d for d in out}
    assert by_name["Anna Wawruszak"].wystapien == 2
    # posortowane po sort_key(family): Pierwszy, Wawruszak, Ostatni? -> alfabet
    families = [d.family for d in out]
    assert families == sorted(families, key=lambda f: __import__(
        "import_sqlite.core.author_names", fromlist=["sort_key"]
    ).sort_key(f))
```

- [ ] **Step 3: Uruchom — ma FAIL**

Run: `uv run pytest src/import_sqlite/tests/test_author_matching.py -q`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 4: Implementacja**

```python
"""Dopasowanie stringów twórców do rekordów ``Autor`` — reużycie
``crossref_bpp.Komparator``. Agregacja distinct-nazwisk (jeden match na
unikalny string, potem rozprowadzenie decyzji na wszystkie patenty).
"""

from collections import Counter
from dataclasses import dataclass, field

from crossref_bpp.core import Komparator, StatusPorownania

from import_sqlite.core.author_names import sort_key, split_name

MAX_KANDYDATOW = 3


@dataclass
class Candidate:
    pk: int
    label: str
    pewnosc: float
    publikacji: int


@dataclass
class DistinctAuthor:
    nazwisko_zrodlowe: str
    given: str
    family: str
    wystapien: int
    status: str
    candidates: list[Candidate] = field(default_factory=list)
    prefill_pk: int | None = None


_STATUS_MAP = {
    StatusPorownania.DOKLADNE: "DOKLADNE",
    StatusPorownania.LUZNE: "LUZNE",
    StatusPorownania.WYMAGA_INGERENCJI: "WYMAGA_INGERENCJI",
}


def match_name(nazwisko_zrodlowe: str) -> DistinctAuthor:
    given, family = split_name(nazwisko_zrodlowe)
    wynik = Komparator.porownaj_author({"family": family, "given": given})

    kandydaci = wynik.kandydaci or []
    candidates = [
        Candidate(
            pk=k.autor.pk,
            label=f"{k.autor.nazwisko} {k.autor.imiona}",
            pewnosc=round(k.pewnosc, 2),
            publikacji=k.publikacji,
        )
        for k in kandydaci[:MAX_KANDYDATOW]
    ]

    status = _STATUS_MAP.get(wynik.status, "BRAK")
    if not candidates:
        status = "BRAK"

    prefill_pk = candidates[0].pk if status == "DOKLADNE" and candidates else None

    return DistinctAuthor(
        nazwisko_zrodlowe=nazwisko_zrodlowe,
        given=given,
        family=family,
        wystapien=0,
        status=status,
        candidates=candidates,
        prefill_pk=prefill_pk,
    )


def aggregate_distinct(name_strings: list[str]) -> list[DistinctAuthor]:
    counts = Counter(s for s in name_strings if s and s.strip())
    result = []
    for nazwisko_zrodlowe, wystapien in counts.items():
        da = match_name(nazwisko_zrodlowe)
        da.wystapien = wystapien
        result.append(da)
    result.sort(key=lambda d: sort_key(d.family))
    return result
```

- [ ] **Step 5: Uruchom — ma PASS**

Run: `uv run pytest src/import_sqlite/tests/test_author_matching.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add src/import_sqlite/core/author_matching.py \
        src/import_sqlite/tests/test_author_matching.py \
        src/import_sqlite/tests/conftest.py
git commit -m "feat(import_sqlite): matching autorow + agregacja distinct (Komparator)"
```

---

### Task 6: IO plików CSV przeglądu

**Files:**
- Create: `src/import_sqlite/review_io.py`
- Test: `src/import_sqlite/tests/test_review_io.py`

**Interfaces:**
- Consumes: `DistinctAuthor`, `Candidate` (Task 5).
- Produces:
  - `write_authors_csv(path: str, authors: list[DistinctAuthor]) -> None` — kolumny: `nazwisko_zrodlowe, given, family, wystapien, status, kandydat_1, kandydat_2, kandydat_3, decyzja`. `decyzja` prefill = `prefill_pk` (str) lub pusty. Kandydat sformatowany: `"Label (#pk, 1.00, 12 publ.)"`.
  - `read_authors_decisions(path: str) -> dict[str, str]` — mapa `nazwisko_zrodlowe -> decyzja` (surowy string, trim). Puste `decyzja` też w mapie (jako `""`).
  - `write_patents_csv(path: str, rows: list[dict]) -> None` — kolumny: `source_id, numer_prawa, numer_zgloszenia, tytul, status, powod`.

- [ ] **Step 1: Napisz failing test**

```python
from import_sqlite.core.author_matching import Candidate, DistinctAuthor
from import_sqlite.review_io import (
    read_authors_decisions,
    write_authors_csv,
    write_patents_csv,
)


def test_authors_csv_roundtrip_decision(tmp_path):
    p = tmp_path / "autorzy.csv"
    authors = [
        DistinctAuthor(
            nazwisko_zrodlowe="Anna Wawruszak",
            given="Anna",
            family="Wawruszak",
            wystapien=3,
            status="DOKLADNE",
            candidates=[Candidate(441, "Wawruszak Anna", 1.0, 12)],
            prefill_pk=441,
        ),
        DistinctAuthor(
            nazwisko_zrodlowe="Jan Kovalski",
            given="Jan",
            family="Kovalski",
            wystapien=1,
            status="BRAK",
            candidates=[],
            prefill_pk=None,
        ),
    ]
    write_authors_csv(str(p), authors)
    decisions = read_authors_decisions(str(p))
    assert decisions["Anna Wawruszak"] == "441"  # prefill DOKLADNE
    assert decisions["Jan Kovalski"] == ""  # brak prefillu


def test_patents_csv_written(tmp_path):
    p = tmp_path / "patenty.csv"
    write_patents_csv(
        str(p),
        [
            {
                "source_id": "UML1",
                "numer_prawa": "Pat.1",
                "numer_zgloszenia": "P.1",
                "tytul": "T",
                "status": "UTWORZONY",
                "powod": "",
            }
        ],
    )
    content = p.read_text(encoding="utf-8")
    assert "UML1" in content and "UTWORZONY" in content
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/import_sqlite/tests/test_review_io.py -q`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implementacja**

```python
"""Odczyt/zapis plików CSV przeglądu (autorzy, patenty).

Czyste IO — bez ORM. UTF-8, przecinek jako separator (Numbers/Excel czytają;
git-diffowalne). ``decyzja`` wypełnia człowiek między ``scan`` a ``apply``.
"""

import csv

from import_sqlite.core.author_matching import Candidate, DistinctAuthor

_AUTORZY_HEADER = [
    "nazwisko_zrodlowe",
    "given",
    "family",
    "wystapien",
    "status",
    "kandydat_1",
    "kandydat_2",
    "kandydat_3",
    "decyzja",
]

_PATENTY_HEADER = ["source_id", "numer_prawa", "numer_zgloszenia", "tytul", "status", "powod"]


def _fmt_candidate(c: Candidate) -> str:
    return f"{c.label} (#{c.pk}, {c.pewnosc:.2f}, {c.publikacji} publ.)"


def write_authors_csv(path: str, authors: list[DistinctAuthor]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(_AUTORZY_HEADER)
        for a in authors:
            kand = [_fmt_candidate(c) for c in a.candidates]
            kand += [""] * (3 - len(kand))
            decyzja = str(a.prefill_pk) if a.prefill_pk else ""
            w.writerow(
                [a.nazwisko_zrodlowe, a.given, a.family, a.wystapien, a.status]
                + kand[:3]
                + [decyzja]
            )


def read_authors_decisions(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("nazwisko_zrodlowe") or "").strip()
            if name:
                out[name] = (row.get("decyzja") or "").strip()
    return out


def write_patents_csv(path: str, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_PATENTY_HEADER)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in _PATENTY_HEADER})
```

- [ ] **Step 4: Uruchom — ma PASS**

Run: `uv run pytest src/import_sqlite/tests/test_review_io.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/import_sqlite/review_io.py src/import_sqlite/tests/test_review_io.py
git commit -m "feat(import_sqlite): IO plikow CSV przegladu (autorzy, patenty)"
```

---

### Task 7: Materializacja patentu do BPP — `apply_patent` (DB)

**Files:**
- Modify: `src/import_sqlite/handlers/patent.py` (dopisać sekcję DB)
- Test: `src/import_sqlite/tests/test_patent_apply.py`

**Interfaces:**
- Consumes: `PatentData` (Task 4), fixtures słownikowe (Task 5 conftest).
- Produces:
  - `@dataclass ImportContext`: `uczelnia`, `obca_jednostka`, `status_korekty`, `zrodlo_informacji`.
  - `build_context() -> ImportContext` — `Uczelnia.objects.get_single_uczelnia_or_fail()`, walidacja `obca_jednostka is not None` (inaczej `CommandError`-friendly `ValueError`), `Status_Korekty` „przed korektą" (fallback `.first()`), `get_or_create` `Zrodlo_Informacji("Import z pliku SQLite (harvester ASB)")`.
  - `resolve_inventor(nazwisko_zrodlowe, decyzja, ctx) -> tuple[Autor, Jednostka, bool]` — zwraca `(autor, jednostka, afiliuje)`. `decyzja="NOWY"` → utwórz `Autor`. pk → pobierz. `jednostka` = `autor.aktualna_jednostka or ctx.obca_jednostka`; `afiliuje = bool(jednostka.skupia_pracownikow)`.
  - `apply_patent(pd: PatentData, decisions: dict[str, str], ctx: ImportContext) -> tuple[str, str]` — zwraca `(status, powod)` gdzie status ∈ `{UTWORZONY, ZAKTUALIZOWANY, WSTRZYMANY}`. Idempotencja po `numer_prawa_wylacznego`. Dedupe twórców per patent po rozwiązanym pk. Owinięte w `transaction.atomic()` (savepoint) — na `ValidationError`/hold rollback tylko tego patentu.

- [ ] **Step 1: Napisz failing test**

```python
import pytest
from model_bakery import baker

from import_sqlite.handlers.patent import PatentData, apply_patent, build_context


@pytest.fixture
def ctx(db, status_korekty):
    from bpp.models import Jednostka, Uczelnia

    uczelnia = baker.make("bpp.Uczelnia", nazwa="UML", skrot="UML")
    obca = baker.make(
        "bpp.Jednostka", nazwa="Obca jednostka", uczelnia=uczelnia,
        skupia_pracownikow=False,
    )
    uczelnia.obca_jednostka = obca
    uczelnia.save()
    return build_context()


def _pd(**kw):
    base = dict(
        source_id="UML1", source_url="http://x/1", tytul="T", rok=2023,
        numer_zgloszenia="P.1", data_zgloszenia=None, numer_prawa="Pat.1",
        data_decyzji=None, szczegoly="", adnotacje="", inventors=["Anna Wawruszak"],
    )
    base.update(kw)
    return PatentData(**base)


@pytest.mark.django_db
def test_apply_creates_patent_with_matched_author(
    ctx, typ_odpowiedzialnosci_aut, charakter_pat, jezyk_polski
):
    from bpp.models import Patent

    jedn = baker.make("bpp.Jednostka", uczelnia=ctx.uczelnia, skupia_pracownikow=True)
    a = baker.make("bpp.Autor", nazwisko="Wawruszak", imiona="Anna",
                   aktualna_jednostka=jedn)
    status, _ = apply_patent(_pd(), {"Anna Wawruszak": str(a.pk)}, ctx)
    assert status == "UTWORZONY"
    p = Patent.objects.get(numer_prawa_wylacznego="Pat.1")
    assert p.rok == 2023
    assert p.wydzial_id == jedn.pk  # 1. twórca z skupia_pracownikow=True
    pa = p.autorzy_set.get()
    assert pa.autor_id == a.pk and pa.afiliuje is True


@pytest.mark.django_db
def test_apply_nowy_creates_author_unaffiliated(
    ctx, typ_odpowiedzialnosci_aut, charakter_pat, jezyk_polski
):
    from bpp.models import Autor, Patent

    status, _ = apply_patent(_pd(), {"Anna Wawruszak": "NOWY"}, ctx)
    assert status == "UTWORZONY"
    a = Autor.objects.get(nazwisko="Wawruszak", imiona="Anna")
    pa = Patent.objects.get(numer_prawa_wylacznego="Pat.1").autorzy_set.get()
    assert pa.autor_id == a.pk and pa.afiliuje is False


@pytest.mark.django_db
def test_apply_holds_on_unresolved_author(
    ctx, typ_odpowiedzialnosci_aut, charakter_pat, jezyk_polski
):
    from bpp.models import Patent

    status, powod = apply_patent(_pd(), {"Anna Wawruszak": ""}, ctx)
    assert status == "WSTRZYMANY"
    assert "Anna Wawruszak" in powod
    assert not Patent.objects.filter(numer_prawa_wylacznego="Pat.1").exists()


@pytest.mark.django_db
def test_apply_dedupes_same_author_twice(
    ctx, typ_odpowiedzialnosci_aut, charakter_pat, jezyk_polski
):
    from bpp.models import Patent

    a = baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    pd = _pd(inventors=["Jan Kowalski", "Jan Kovalski"])
    decisions = {"Jan Kowalski": str(a.pk), "Jan Kovalski": str(a.pk)}
    status, _ = apply_patent(pd, decisions, ctx)
    assert status == "UTWORZONY"
    p = Patent.objects.get(numer_prawa_wylacznego="Pat.1")
    assert p.autorzy_set.count() == 1  # zdeduplikowane, brak IntegrityError


@pytest.mark.django_db
def test_apply_idempotent_update(
    ctx, typ_odpowiedzialnosci_aut, charakter_pat, jezyk_polski
):
    from bpp.models import Patent

    a = baker.make("bpp.Autor", nazwisko="Wawruszak", imiona="Anna")
    apply_patent(_pd(), {"Anna Wawruszak": str(a.pk)}, ctx)
    status, _ = apply_patent(_pd(tytul="Nowy tytuł"), {"Anna Wawruszak": str(a.pk)}, ctx)
    assert status == "ZAKTUALIZOWANY"
    assert Patent.objects.filter(numer_prawa_wylacznego="Pat.1").count() == 1
    assert Patent.objects.get(numer_prawa_wylacznego="Pat.1").tytul_oryginalny == "Nowy tytuł"
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/import_sqlite/tests/test_patent_apply.py -q`
Expected: FAIL (ImportError: apply_patent, build_context).

- [ ] **Step 3: Implementacja (dopisz do `handlers/patent.py`)**

```python
# --- sekcja DB (na dole handlers/patent.py) ---

from dataclasses import dataclass as _dataclass

from django.core.exceptions import ValidationError
from django.db import transaction

from bpp.util import safe_html


@_dataclass
class ImportContext:
    uczelnia: object
    obca_jednostka: object
    status_korekty: object
    zrodlo_informacji: object


def build_context() -> "ImportContext":
    from bpp.models import Status_Korekty, Uczelnia, Zrodlo_Informacji

    uczelnia = Uczelnia.objects.get_single_uczelnia_or_fail()
    if uczelnia.obca_jednostka is None:
        raise ValueError(
            "Uczelnia nie ma ustawionej 'obca_jednostka' — ustaw ją w adminie "
            "przed importem (potrzebna jako jednostka twórców spoza uczelni)."
        )
    status = (
        Status_Korekty.objects.filter(nazwa="przed korektą").first()
        or Status_Korekty.objects.first()
    )
    zrodlo, _ = Zrodlo_Informacji.objects.get_or_create(nazwa="Import z pliku SQLite (harvester ASB)")
    return ImportContext(uczelnia, uczelnia.obca_jednostka, status, zrodlo)


def resolve_inventor(nazwisko_zrodlowe, decyzja, ctx):
    """Zwróć (autor, jednostka, afiliuje) dla rozstrzygniętego twórcy."""
    from bpp.models import Autor

    from import_sqlite.core.author_names import split_name

    if decyzja == "NOWY":
        given, family = split_name(nazwisko_zrodlowe)
        autor = Autor.objects.create(imiona=given, nazwisko=family)
        autor.dodaj_jednostke(ctx.obca_jednostka)
        jednostka = ctx.obca_jednostka
    else:
        autor = Autor.objects.get(pk=int(decyzja))
        jednostka = autor.aktualna_jednostka or ctx.obca_jednostka
    return autor, jednostka, bool(jednostka.skupia_pracownikow)


def apply_patent(pd: PatentData, decisions: dict, ctx) -> tuple[str, str]:
    from bpp.models import Patent

    # 1. Rozstrzygnij WSZYSTKICH twórców, dedupe po pk (pierwsze wystąpienie wygrywa)
    resolved = []  # (autor, jednostka, afiliuje, zapisany_jako)
    seen_pk = set()
    for nazwisko_zrodlowe in pd.inventors:
        decyzja = decisions.get(nazwisko_zrodlowe, "")
        if not decyzja:
            return ("WSTRZYMANY", f"nierozstrzygnięty twórca: {nazwisko_zrodlowe}")

    try:
        with transaction.atomic():
            existing = list(
                Patent.objects.filter(numer_prawa_wylacznego=pd.numer_prawa)
            )
            if len(existing) > 1:
                return ("WSTRZYMANY", "niejednoznaczny klucz numer_prawa_wylacznego")

            for kolejnosc, nazwisko_zrodlowe in enumerate(pd.inventors):
                autor, jednostka, afiliuje = resolve_inventor(
                    nazwisko_zrodlowe, decisions[nazwisko_zrodlowe], ctx
                )
                if autor.pk in seen_pk:
                    continue
                seen_pk.add(autor.pk)
                resolved.append((autor, jednostka, afiliuje, nazwisko_zrodlowe, kolejnosc))

            wydzial = next(
                (j for (_a, j, _af, _z, _k) in resolved if j.skupia_pracownikow),
                None,
            )

            if existing:
                patent = existing[0]
                patent.autorzy_set.all().delete()
                created = False
            else:
                patent = Patent()
                created = True

            patent.tytul_oryginalny = safe_html(pd.tytul)
            patent.rok = pd.rok
            patent.numer_zgloszenia = pd.numer_zgloszenia or None
            patent.data_zgloszenia = pd.data_zgloszenia
            patent.numer_prawa_wylacznego = pd.numer_prawa
            patent.data_decyzji = pd.data_decyzji
            patent.wydzial = wydzial
            patent.www = pd.source_url
            patent.szczegoly = pd.szczegoly
            patent.adnotacje = pd.adnotacje
            patent.status_korekty = ctx.status_korekty
            patent.informacja_z = ctx.zrodlo_informacji
            patent.save()

            for autor, jednostka, afiliuje, zapisany_jako, kolejnosc in resolved:
                patent.dodaj_autora(
                    autor,
                    jednostka,
                    zapisany_jako=zapisany_jako,
                    kolejnosc=kolejnosc,
                    afiliuje=afiliuje,
                )
    except ValidationError as e:
        return ("WSTRZYMANY", f"ValidationError: {e}")

    return ("UTWORZONY" if created else "ZAKTUALIZOWANY", "")
```

Uwaga implementacyjna: pierwszej pętli (walidacja rozstrzygnięcia) NIE łącz z
transakcją — hold przy braku decyzji ma się zdarzyć PRZED utworzeniem czegokolwiek.

- [ ] **Step 4: Uruchom — ma PASS**

Run: `uv run pytest src/import_sqlite/tests/test_patent_apply.py -q`
Expected: PASS (5 passed). Wymaga bazy z rozszerzeniem `unaccent` (testcontainers to zapewniają).

- [ ] **Step 5: Commit**

```bash
git add src/import_sqlite/handlers/patent.py src/import_sqlite/tests/test_patent_apply.py
git commit -m "feat(import_sqlite): apply_patent - tworzenie/aktualizacja Patent + tw/dedupe"
```

---

### Task 8: Komenda `import_sqlite_scan`

**Files:**
- Create: `src/import_sqlite/management/commands/import_sqlite_scan.py`
- Test: `src/import_sqlite/tests/test_scan_command.py`

**Interfaces:**
- Consumes: `iter_records` (Task 3), `parse_patent` (Task 4), `aggregate_distinct` (Task 5), `write_authors_csv`/`write_patents_csv` (Task 6).
- Produces: management command `import_sqlite_scan <sqlite> --typ patent --out-autorzy PATH --out-patenty PATH`. Zbiera wszystkie `inventors` ze wszystkich patentów, agreguje distinct, zapisuje oba CSV-e. Patenty w CSV dostają status `DO_IMPORTU`.

- [ ] **Step 1: Napisz failing test**

```python
import json
import sqlite3

import pytest
from django.core.management import call_command
from model_bakery import baker


def _db(tmp_path, patents):
    p = tmp_path / "ppm.sqlite3"
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE records (type TEXT, source_id TEXT, source_url TEXT, parsed_json TEXT)")
    for i, pj in enumerate(patents):
        con.execute(
            "INSERT INTO records (type, source_id, source_url, parsed_json) VALUES (?,?,?,?)",
            ("patent", f"UML{i}", f"http://x/{i}", json.dumps(pj)),
        )
    con.commit()
    con.close()
    return str(p)


@pytest.mark.django_db
def test_scan_writes_both_csvs(tmp_path):
    baker.make("bpp.Autor", nazwisko="Wawruszak", imiona="Anna")
    db = _db(tmp_path, [
        {"title": "T1", "inventors": ["Anna Wawruszak", "Jan Kovalski"],
         "application_number": "P.1", "application_date": "01-01-2023",
         "all_fields": {"Numer patentu/prawa": "Pat.1"}},
    ])
    out_a = tmp_path / "autorzy.csv"
    out_p = tmp_path / "patenty.csv"
    call_command("import_sqlite_scan", db, "--typ", "patent",
                 "--out-autorzy", str(out_a), "--out-patenty", str(out_p))
    a_text = out_a.read_text(encoding="utf-8")
    assert "Anna Wawruszak" in a_text and "Jan Kovalski" in a_text
    assert "DOKLADNE" in a_text  # Anna dopasowana
    assert "Pat.1" in out_p.read_text(encoding="utf-8")
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/import_sqlite/tests/test_scan_command.py -q`
Expected: FAIL (Unknown command: 'import_sqlite_scan').

- [ ] **Step 3: Implementacja**

```python
from django.core.management.base import BaseCommand

from import_sqlite.core.author_matching import aggregate_distinct
from import_sqlite.handlers.patent import parse_patent
from import_sqlite.reader import iter_records
from import_sqlite.review_io import write_authors_csv, write_patents_csv


class Command(BaseCommand):
    help = "Skanuje plik sqlite (harvester) i wypisuje CSV-e do przeglądu."

    def add_arguments(self, parser):
        parser.add_argument("sqlite_path")
        parser.add_argument("--typ", default="patent")
        parser.add_argument("--out-autorzy", default="autorzy_do_uzgodnienia.csv")
        parser.add_argument("--out-patenty", default="patenty_do_przegladu.csv")

    def handle(self, *args, **opts):
        records = list(iter_records(opts["sqlite_path"], opts["typ"]))
        patents = [parse_patent(r) for r in records]

        all_names = [name for pd in patents for name in pd.inventors]
        authors = aggregate_distinct(all_names)
        write_authors_csv(opts["out_autorzy"], authors)

        write_patents_csv(
            opts["out_patenty"],
            [
                {
                    "source_id": pd.source_id,
                    "numer_prawa": pd.numer_prawa,
                    "numer_zgloszenia": pd.numer_zgloszenia,
                    "tytul": pd.tytul,
                    "status": "DO_IMPORTU",
                    "powod": "",
                }
                for pd in patents
            ],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{len(patents)} patentów, {len(authors)} unikalnych twórców. "
                f"Wypełnij kolumnę 'decyzja' w {opts['out_autorzy']}."
            )
        )
```

- [ ] **Step 4: Uruchom — ma PASS**

Run: `uv run pytest src/import_sqlite/tests/test_scan_command.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add src/import_sqlite/management/commands/import_sqlite_scan.py \
        src/import_sqlite/tests/test_scan_command.py
git commit -m "feat(import_sqlite): komenda scan -> CSV-e przegladu"
```

---

### Task 9: Komenda `import_sqlite_apply` + walidacja decyzji + denorm flush

**Files:**
- Create: `src/import_sqlite/management/commands/import_sqlite_apply.py`
- Test: `src/import_sqlite/tests/test_apply_command.py`

**Interfaces:**
- Consumes: `iter_records`, `parse_patent`, `read_authors_decisions`, `write_patents_csv`, `build_context`, `apply_patent`.
- Produces: komenda `import_sqlite_apply <sqlite> --typ patent --autorzy PATH [--out-patenty PATH] [--dry-run]`. Waliduje decyzje (każdy pk musi istnieć — przed transakcją). Pętla po patentach; zbiera statusy; `denorms.flush()` na końcu (poza dry-run); przy `--dry-run` rollback całości. Nadpisuje `--out-patenty` finalnymi statusami.

- [ ] **Step 1: Napisz failing test**

```python
import json
import sqlite3

import pytest
from django.core.management import call_command
from model_bakery import baker


def _db(tmp_path, patents):
    p = tmp_path / "ppm.sqlite3"
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE records (type TEXT, source_id TEXT, source_url TEXT, parsed_json TEXT)")
    for i, pj in enumerate(patents):
        con.execute(
            "INSERT INTO records (type, source_id, source_url, parsed_json) VALUES (?,?,?,?)",
            ("patent", f"UML{i}", f"http://x/{i}", json.dumps(pj)),
        )
    con.commit(); con.close()
    return str(p)


@pytest.fixture
def uczelnia_setup(db, status_korekty):
    u = baker.make("bpp.Uczelnia", nazwa="UML", skrot="UML")
    obca = baker.make("bpp.Jednostka", nazwa="Obca", uczelnia=u, skupia_pracownikow=False)
    u.obca_jednostka = obca; u.save()
    return u


@pytest.mark.django_db
def test_apply_creates_patent_from_csv(
    tmp_path, uczelnia_setup, typ_odpowiedzialnosci_aut, charakter_pat, jezyk_polski
):
    from bpp.models import Patent

    a = baker.make("bpp.Autor", nazwisko="Wawruszak", imiona="Anna")
    db = _db(tmp_path, [
        {"title": "T1", "inventors": ["Anna Wawruszak"], "application_number": "P.1",
         "application_date": "01-01-2023", "all_fields": {"Numer patentu/prawa": "Pat.1"}},
    ])
    autorzy = tmp_path / "autorzy.csv"
    autorzy.write_text(
        "nazwisko_zrodlowe,given,family,wystapien,status,kandydat_1,kandydat_2,kandydat_3,decyzja\n"
        f"Anna Wawruszak,Anna,Wawruszak,1,DOKLADNE,,,,{a.pk}\n",
        encoding="utf-8",
    )
    call_command("import_sqlite_apply", db, "--typ", "patent",
                 "--autorzy", str(autorzy), "--out-patenty", str(tmp_path / "out.csv"))
    assert Patent.objects.filter(numer_prawa_wylacznego="Pat.1").count() == 1


@pytest.mark.django_db
def test_apply_dry_run_persists_nothing(
    tmp_path, uczelnia_setup, typ_odpowiedzialnosci_aut, charakter_pat, jezyk_polski
):
    from bpp.models import Patent

    a = baker.make("bpp.Autor", nazwisko="Wawruszak", imiona="Anna")
    db = _db(tmp_path, [
        {"title": "T1", "inventors": ["Anna Wawruszak"], "application_number": "P.1",
         "application_date": "01-01-2023", "all_fields": {"Numer patentu/prawa": "Pat.1"}},
    ])
    autorzy = tmp_path / "autorzy.csv"
    autorzy.write_text(
        "nazwisko_zrodlowe,given,family,wystapien,status,kandydat_1,kandydat_2,kandydat_3,decyzja\n"
        f"Anna Wawruszak,Anna,Wawruszak,1,DOKLADNE,,,,{a.pk}\n",
        encoding="utf-8",
    )
    call_command("import_sqlite_apply", db, "--typ", "patent",
                 "--autorzy", str(autorzy), "--dry-run",
                 "--out-patenty", str(tmp_path / "out.csv"))
    assert not Patent.objects.filter(numer_prawa_wylacznego="Pat.1").exists()


@pytest.mark.django_db
def test_apply_rejects_nonexistent_pk(
    tmp_path, uczelnia_setup, typ_odpowiedzialnosci_aut, charakter_pat, jezyk_polski
):
    from django.core.management.base import CommandError

    db = _db(tmp_path, [
        {"title": "T1", "inventors": ["Anna Wawruszak"], "application_number": "P.1",
         "application_date": "01-01-2023", "all_fields": {"Numer patentu/prawa": "Pat.1"}},
    ])
    autorzy = tmp_path / "autorzy.csv"
    autorzy.write_text(
        "nazwisko_zrodlowe,given,family,wystapien,status,kandydat_1,kandydat_2,kandydat_3,decyzja\n"
        "Anna Wawruszak,Anna,Wawruszak,1,DOKLADNE,,,,99999999\n",
        encoding="utf-8",
    )
    with pytest.raises(CommandError):
        call_command("import_sqlite_apply", db, "--typ", "patent",
                     "--autorzy", str(autorzy), "--out-patenty", str(tmp_path / "out.csv"))
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/import_sqlite/tests/test_apply_command.py -q`
Expected: FAIL (Unknown command).

- [ ] **Step 3: Implementacja**

```python
from denorm import denorms
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from bpp.models import Autor
from import_sqlite.handlers.patent import apply_patent, build_context, parse_patent
from import_sqlite.reader import iter_records
from import_sqlite.review_io import read_authors_decisions, write_patents_csv


class Command(BaseCommand):
    help = "Importuje patenty z sqlite do BPP wg decyzji z CSV autorów."

    def add_arguments(self, parser):
        parser.add_argument("sqlite_path")
        parser.add_argument("--typ", default="patent")
        parser.add_argument("--autorzy", required=True)
        parser.add_argument("--out-patenty", default="patenty_do_przegladu.csv")
        parser.add_argument("--dry-run", action="store_true")

    def _validate_pks(self, decisions):
        pks = {
            int(v) for v in decisions.values()
            if v and v != "NOWY" and v.isdigit()
        }
        istniejace = set(
            Autor.objects.filter(pk__in=pks).values_list("pk", flat=True)
        )
        brakujace = pks - istniejace
        if brakujace:
            raise CommandError(
                f"decyzja wskazuje nieistniejące pk Autora: {sorted(brakujace)}"
            )
        zle = [
            v for v in decisions.values()
            if v and v != "NOWY" and not v.isdigit()
        ]
        if zle:
            raise CommandError(f"nieprawidłowe wartości 'decyzja': {zle}")

    def handle(self, *args, **opts):
        decisions = read_authors_decisions(opts["autorzy"])
        self._validate_pks(decisions)

        ctx = build_context()
        records = list(iter_records(opts["sqlite_path"], opts["typ"]))
        patents = [parse_patent(r) for r in records]

        rows = []
        counts = {}
        try:
            with transaction.atomic():
                for pd in patents:
                    status, powod = apply_patent(pd, decisions, ctx)
                    counts[status] = counts.get(status, 0) + 1
                    rows.append({
                        "source_id": pd.source_id, "numer_prawa": pd.numer_prawa,
                        "numer_zgloszenia": pd.numer_zgloszenia, "tytul": pd.tytul,
                        "status": status, "powod": powod,
                    })
                if not opts["dry_run"]:
                    denorms.flush()
                if opts["dry_run"]:
                    transaction.set_rollback(True)
        finally:
            write_patents_csv(opts["out_patenty"], rows)

        prefix = "[DRY-RUN] " if opts["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(prefix + str(counts)))
```

- [ ] **Step 4: Uruchom — ma PASS**

Run: `uv run pytest src/import_sqlite/tests/test_apply_command.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/import_sqlite/management/commands/import_sqlite_apply.py \
        src/import_sqlite/tests/test_apply_command.py
git commit -m "feat(import_sqlite): komenda apply + walidacja decyzji + denorm flush"
```

---

### Task 10: Newsfragment + pełny przebieg testów apki

**Files:**
- Create: `newsfragments/<NNN>.feature` (numer z otwartego zgłoszenia lub `+import-sqlite`)
- Test: cała apka.

- [ ] **Step 1: Newsfragment**

Utwórz `newsfragments/+import-sqlite-patenty.feature`:

```
Nowa aplikacja ``import_sqlite``: import patentów z plików SQLite z harvesterów
(polecenia ``import_sqlite_scan`` / ``import_sqlite_apply``) z dopasowaniem
twórców do rekordów Autor i ręcznym uzgadnianiem przez CSV.
```

- [ ] **Step 2: Cała apka — testy**

Run: `uv run pytest src/import_sqlite/ -q`
Expected: PASS (wszystkie).

- [ ] **Step 3: Ruff**

Run: `ruff format src/import_sqlite/ && ruff check src/import_sqlite/`
Expected: brak błędów (popraw ręcznie, jeśli są).

- [ ] **Step 4: Commit**

```bash
git add newsfragments/+import-sqlite-patenty.feature
git commit -m "docs(newsfragment): aplikacja import_sqlite (import patentow z harvestera)"
```

---

## Self-Review

**Spec coverage:**
- §2 decyzje: kształt (Task 1,8,9), NOWY-opt-in (Task 7 `resolve_inventor`), klucz `numer_prawa_wylacznego` (Task 7 idempotencja), rok+fallback (Task 4), wydzial po `skupia_pracownikow` (Task 7), punktacja pominięta (nie mapujemy), metadane→szczegoly/adnotacje (Task 4). ✓
- §3 architektura: pliki reader/core/handlers/review_io/commands (Task 1–9). ✓
- §5.1 split (Task 2), §5.2 distinct (Task 5), §5.3 CSV + status BLAD→BRAK (Task 5,6), §5.4 afiliacja (Task 7), §5.5 dedupe (Task 7). ✓
- §6 wstrzymanie (Task 7 hold + Validationation catch), savepoint (Task 7 atomic). ✓
- §7 mapowanie + idempotencja + denorm flush (Task 4,7,9). ✓
- §8 testy: wszystkie 13 przypadków rozdzielone między Task 2–9. ✓
- §9 rejestracja + precondition obca_jednostka (Task 1, Task 7 build_context). ✓

**Placeholder scan:** brak TBD/TODO; każdy krok ma realny kod. ✓

**Type consistency:** `RawRecord`(Task 3)→`parse_patent`(Task 4)→`PatentData`; `DistinctAuthor`/`Candidate`(Task 5)→`review_io`(Task 6); `ImportContext`/`apply_patent`(Task 7)→`apply` command(Task 9). Nazwy spójne. ✓

**Uwaga wykonawcza (do naprawy w Task 7 podczas implementacji):** w szkicu
`apply_patent` pierwsza pętla walidacji rozstrzygnięcia współdzieli zmienne z
pętlą właściwą — przy implementacji rozdziel je czytelnie (walidacja braków
PRZED `transaction.atomic`, materializacja w środku), zgodnie z uwagą pod
Step 3. To jedyny punkt wymagający uwagi, nie placeholder.
