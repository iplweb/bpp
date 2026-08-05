# Pivot (tabela krzyżowa) w multiseek — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dodać do wyszukiwarki multiseek raport „tabela krzyżowa" (pivot):
grupowanie wyników w macierz Wiersze × Kolumny z wybieraną metryką w
komórce i sumami brzegowymi — pokrywa jednocześnie „Szukaj → Multiseek"
i „prace autora" (ten sam silnik).

**Architecture:** Nowy `report_type="pivot"` w rejestrze multiseek.
Konfiguracja pivota (wiersz/kolumna/metryka) czytana z parametrów GET na
URL wyników. Cała logika agregacji w nowym module
`src/bpp/multiseek_registry/pivot.py` (`zbuduj_pivot()` + rejestry
wymiarów/metryk + `PivotResult`), wpięta w `MyMultiseekResults.get_context_data`.
Nowy partial `report-body-pivot.html` renderuje macierz; eksport XLSX/CSV
buduje z tej samej struktury `PivotResult`.

**Tech Stack:** Django, PostgreSQL (widoki materializowane `bpp_rekord_mat`
/ `bpp_autorzy_mat`), `django_multiseek`, pytest + model_bakery, openpyxl
(eksport XLSX), Foundation CSS + SCSS/grunt.

## Global Constraints

- Python `uv run` prefix dla WSZYSTKICH poleceń python/pytest. Nigdy gołe `python`.
- Max długość linii: 88 znaków (ruff).
- Testy: pytest (funkcje, nie klasy), `@pytest.mark.django_db`,
  `model_bakery.baker.make`, `-n auto`. Output testów do pliku w
  `/tmp`, grep — nigdy dwa razy ten sam przebieg.
- **Bez migracji, bez zmian modeli.** Tylko istniejące pola `Rekord`/`Autorzy`.
- Django komentarze `{# … #}` jedno-liniowe (każda linia własne `{# #}`).
- Ikony: publiczny frontend = Foundation-Icons (`<span class="fi-icon"/>`).
- Newsfragment po zmianie: `src/bpp/newsfragments/<slug>.feature.rst` (po polsku).
- `Rekord.id` to `TupleField(IntegerField(), size=2, primary_key=True)`
  (`src/bpp/models/cache/rekord.py:212`) — `Count("id")` działa na PG.
- `report_type` to **indeks pozycyjny** — nowy typ MUSI iść na KONIEC listy
  `multiseek_report_types`, `public=True`.
- **KRYTYCZNE:** przed `.values().annotate()` czyścić ordering
  (`base_qs.order_by()`) — inaczej `default_ordering=["-rok"]` / sort
  formularza wchodzi do GROUP BY (K3).

Pełny kontekst decyzji: spec
`docs/superpowers/specs/2026-07-24-multiseek-pivot-grupowanie-design.md`.

---

## File Structure

- **Create** `src/bpp/multiseek_registry/pivot.py` — rejestry wymiarów
  (`DIMENSIONS`) i metryk (`METRICS`), `PivotDimension`, `PivotMetric`,
  `PivotResult`, `parse_pivot_params(GET)`, `zbuduj_pivot(base_qs, row, col, metric)`.
- **Create** `src/django_bpp/templates/multiseek/report-body-pivot.html` —
  pasek selektorów (GET) + tabela krzyżowa + adnotacja o dublowaniu.
- **Create** `src/bpp/tests/test_multiseek_pivot.py` — testy jednostkowe
  `zbuduj_pivot`/`parse_pivot_params`.
- **Create** `src/bpp/tests/test_multiseek_pivot_view.py` — testy widoku
  i eksportu pivota.
- **Modify** `src/bpp/multiseek_registry/reports.py:8` — dopisać
  `ReportType("pivot", "tabela krzyżowa")` na końcu listy.
- **Modify** `src/bpp/views/mymultiseek.py` — `get_context_data` (gałąź
  pivota, ~:181), `MyMultiseekExport.get`/`_export_data` (gałąź pivota,
  omija cap 5000, ~:247).
- **Modify** `src/django_bpp/templates/multiseek/common-results.html:9` —
  gałąź `report_type == "pivot"` przed gate'em 25000 i paginacją.
- **Modify** `src/bpp/views/multiseek_export.py` — builder
  `pivot_xlsx_export_response` / `pivot_csv_export_response` z `PivotResult`.
- **Modify** (SCSS) komponent stylu tabeli krzyżowej — plik wskaże Task 4.
- **Create** `src/bpp/newsfragments/<slug>.feature.rst`.

---

## Task 1: Rejestry wymiarów/metryk + walidacja GET (`pivot.py` szkielet)

**Files:**
- Create: `src/bpp/multiseek_registry/pivot.py`
- Test: `src/bpp/tests/test_multiseek_pivot.py`

**Interfaces:**
- Produces:
  - `@dataclass PivotDimension(key:str, label:str, expr:str, allow_column:bool=True, autorzy:bool=False, label_kind:str="raw")`
    — `label_kind ∈ {"raw","fk","choices_charakter_ogolny","pk_bucket","autor"}`;
    dla `label_kind=="fk"` dochodzi pole `fk_model` (klasa modelu) i
    `fk_label_field:str="nazwa"`.
  - `@dataclass PivotMetric(key:str, label:str, field:str|None)` —
    `field is None` → metryka „liczba" (Count), inaczej `Sum(field)`.
  - `DIMENSIONS: dict[str, PivotDimension]`, `METRICS: dict[str, PivotMetric]`.
  - `DEFAULT_ROW="rok"`, `DEFAULT_METRIC="liczba"`.
  - `parse_pivot_params(GET) -> tuple[PivotDimension, PivotDimension|None, PivotMetric]`
    — czyta `pivot_row`/`pivot_col`/`pivot_val`; nieznany/pusty `pivot_row`
    → `DIMENSIONS[DEFAULT_ROW]`; `pivot_col` pusty lub niedozwolony jako
    kolumna (`allow_column==False`) lub równy wierszowi → `None`; nieznany
    `pivot_val` → `METRICS[DEFAULT_METRIC]`.

- [ ] **Step 1: Napisz failing test walidacji parametrów**

```python
# src/bpp/tests/test_multiseek_pivot.py
from bpp.multiseek_registry import pivot


def test_parse_pivot_params_defaults_when_empty():
    row, col, metric = pivot.parse_pivot_params({})
    assert row.key == "rok"
    assert col is None
    assert metric.key == "liczba"


def test_parse_pivot_params_unknown_keys_fall_back():
    row, col, metric = pivot.parse_pivot_params(
        {"pivot_row": "xxx", "pivot_col": "yyy", "pivot_val": "zzz"}
    )
    assert row.key == "rok"
    assert col is None
    assert metric.key == "liczba"


def test_parse_pivot_params_column_must_allow_column():
    # "jednostka" jest tylko wierszem (allow_column=False) → col=None
    row, col, metric = pivot.parse_pivot_params(
        {"pivot_row": "rok", "pivot_col": "jednostka", "pivot_val": "liczba"}
    )
    assert col is None


def test_parse_pivot_params_column_equal_to_row_dropped():
    row, col, metric = pivot.parse_pivot_params(
        {"pivot_row": "rok", "pivot_col": "rok"}
    )
    assert col is None


def test_parse_pivot_params_valid_crosstab():
    row, col, metric = pivot.parse_pivot_params(
        {"pivot_row": "rok", "pivot_col": "charakter_ogolny", "pivot_val": "punkty_kbn"}
    )
    assert (row.key, col.key, metric.key) == ("rok", "charakter_ogolny", "punkty_kbn")
```

- [ ] **Step 2: Uruchom test — ma paść (ImportError/AttributeError)**

Run: `uv run pytest src/bpp/tests/test_multiseek_pivot.py -p no:cacheprovider -q 2>&1 | tee /tmp/pivot_t1.log; grep -E "passed|failed|error" /tmp/pivot_t1.log | tail -3`
Expected: FAIL — `module 'bpp.multiseek_registry.pivot' has no attribute 'parse_pivot_params'`.

- [ ] **Step 3: Zaimplementuj `pivot.py` (rejestry + parse)**

```python
# src/bpp/multiseek_registry/pivot.py
from dataclasses import dataclass, field

from bpp.models.system.charakter_formalny import CHARAKTER_OGOLNY_CHOICES


@dataclass(frozen=True)
class PivotDimension:
    key: str
    label: str
    expr: str
    allow_column: bool = True
    autorzy: bool = False
    label_kind: str = "raw"          # raw|fk|choices_charakter_ogolny|pk_bucket|autor
    fk_model: type | None = None
    fk_label_field: str = "nazwa"


@dataclass(frozen=True)
class PivotMetric:
    key: str
    label: str
    field: str | None                # None → Count("id"); inaczej Sum(field)


def _fk(model_path, label_field="nazwa"):
    # lazy import, żeby uniknąć cykli przy ładowaniu rejestru
    from django.apps import apps

    return apps.get_model(*model_path.split("."))


DEFAULT_ROW = "rok"
DEFAULT_METRIC = "liczba"

# UWAGA: expr dla wymiarów FK to "<pole>_id" — values() zwraca surowe id,
# etykiety dociągamy hurtowo w zbuduj_pivot (label_kind="fk").
DIMENSIONS: dict[str, PivotDimension] = {
    "rok": PivotDimension("rok", "Rok", "rok"),
    "charakter_formalny": PivotDimension(
        "charakter_formalny", "Charakter formalny", "charakter_formalny_id",
        label_kind="fk", fk_model=_fk("bpp.Charakter_Formalny"),
    ),
    "charakter_ogolny": PivotDimension(
        "charakter_ogolny", "Charakter ogólny (rodzaj)",
        "charakter_formalny__charakter_ogolny",
        label_kind="choices_charakter_ogolny",
    ),
    "typ_kbn": PivotDimension(
        "typ_kbn", "Typ MNiSW/MEiN", "typ_kbn_id",
        label_kind="fk", fk_model=_fk("bpp.Typ_KBN"),
    ),
    "koszyk_pk": PivotDimension(
        "koszyk_pk", "Koszyk punktów PK", "punkty_kbn", label_kind="pk_bucket",
    ),
    "jezyk": PivotDimension(
        "jezyk", "Język", "jezyk_id",
        label_kind="fk", fk_model=_fk("bpp.Jezyk"),
    ),
    "zrodlo": PivotDimension(
        "zrodlo", "Źródło", "zrodlo_id", allow_column=False,
        label_kind="fk", fk_model=_fk("bpp.Zrodlo"),
    ),
    "jednostka": PivotDimension(
        "jednostka", "Jednostka", "autorzy__jednostka_id", allow_column=False,
        autorzy=True, label_kind="fk", fk_model=_fk("bpp.Jednostka"),
    ),
    "dyscyplina": PivotDimension(
        "dyscyplina", "Dyscyplina naukowa", "autorzy__dyscyplina_naukowa_id",
        autorzy=True, label_kind="fk",
        fk_model=_fk("bpp.Dyscyplina_Naukowa"),
    ),
    "autor": PivotDimension(
        "autor", "Autor", "autorzy__autor_id", allow_column=False,
        autorzy=True, label_kind="autor", fk_model=_fk("bpp.Autor"),
    ),
}

METRICS: dict[str, PivotMetric] = {
    "liczba": PivotMetric("liczba", "Liczba prac", None),
    "punkty_kbn": PivotMetric("punkty_kbn", "Σ punkty PK", "punkty_kbn"),
    "impact_factor": PivotMetric("impact_factor", "Σ Impact Factor", "impact_factor"),
    "liczba_cytowan": PivotMetric("liczba_cytowan", "Σ liczba cytowań", "liczba_cytowan"),
    "punktacja_wewnetrzna": PivotMetric(
        "punktacja_wewnetrzna", "Σ punktacja wewnętrzna", "punktacja_wewnetrzna"
    ),
}


def parse_pivot_params(GET):
    row = DIMENSIONS.get(GET.get("pivot_row") or "", DIMENSIONS[DEFAULT_ROW])
    metric = METRICS.get(GET.get("pivot_val") or "", METRICS[DEFAULT_METRIC])
    col_key = GET.get("pivot_col") or ""
    col = DIMENSIONS.get(col_key)
    if col is not None and (not col.allow_column or col.key == row.key):
        col = None
    return row, col, metric
```

- [ ] **Step 4: Uruchom testy — mają przejść**

Run: `uv run pytest src/bpp/tests/test_multiseek_pivot.py -p no:cacheprovider -q 2>&1 | tee /tmp/pivot_t1.log; grep -E "passed|failed|error" /tmp/pivot_t1.log | tail -3`
Expected: PASS (5 passed).

- [ ] **Step 5: ruff + commit**

```bash
uv run ruff format src/bpp/multiseek_registry/pivot.py src/bpp/tests/test_multiseek_pivot.py
uv run ruff check src/bpp/multiseek_registry/pivot.py src/bpp/tests/test_multiseek_pivot.py
git add src/bpp/multiseek_registry/pivot.py src/bpp/tests/test_multiseek_pivot.py
git commit -m "feat(multiseek): rejestry wymiarów/metryk pivota + walidacja GET"
```

---

## Task 2: `zbuduj_pivot()` — agregacja (strategia A/B) + etykiety

**Files:**
- Modify: `src/bpp/multiseek_registry/pivot.py`
- Test: `src/bpp/tests/test_multiseek_pivot.py`

**Interfaces:**
- Consumes: `PivotDimension`, `PivotMetric`, `DIMENSIONS`, `METRICS` (Task 1).
- Produces:
  - `@dataclass PivotResult(rows, cols, cells, row_totals, col_totals, grand_total, row_dim, col_dim, metric, has_autorzy_dim)`
    gdzie `rows`/`cols` to listy `(key, label)` posortowane; `cells` to
    `dict[(row_key, col_key) -> number]` (`col_key is None` gdy brak
    kolumn); `row_totals`/`col_totals` to `dict[key -> number]`;
    `grand_total` liczba; `has_autorzy_dim: bool`.
  - `zbuduj_pivot(base_qs, row_dim, col_dim, metric) -> PivotResult`.

**Strategia (patrz spec §8):** wyczyść ordering (`base_qs.order_by()`).
Jeśli `row_dim.autorzy` lub (`col_dim` i `col_dim.autorzy`) → **strategia B**
(unikatowe pary + agregacja w Pythonie). Inaczej → **strategia A** (dedup
rekordów przez `pk__in`, `values().annotate()`).

- [ ] **Step 1: Failing test — strategia A, liczba prac (rok × charakter ogólny)**

```python
# dopisz do src/bpp/tests/test_multiseek_pivot.py
import pytest
from model_bakery import baker

from bpp.models import Charakter_Formalny
from bpp.models.const import CHARAKTER_OGOLNY_ARTYKUL, CHARAKTER_OGOLNY_ROZDZIAL


@pytest.fixture
def rekordy_pivot(db):
    from bpp.models.cache import Rekord

    art = baker.make(Charakter_Formalny, charakter_ogolny=CHARAKTER_OGOLNY_ARTYKUL)
    roz = baker.make(Charakter_Formalny, charakter_ogolny=CHARAKTER_OGOLNY_ROZDZIAL)
    # helper tworzący wpis w bpp_rekord_mat: użyj istniejących fabryk projektu
    # (baker.make(Wydawnictwo_Ciagle/Zwarte) + odświeżenie widoku), patrz
    # src/bpp/tests/ — fixture zwraca queryset Rekord.objects.all()
    ...
    return Rekord.objects.all()


@pytest.mark.django_db
def test_zbuduj_pivot_a_liczba(rekordy_pivot):
    from bpp.multiseek_registry import pivot

    res = pivot.zbuduj_pivot(
        rekordy_pivot,
        pivot.DIMENSIONS["rok"],
        pivot.DIMENSIONS["charakter_ogolny"],
        pivot.METRICS["liczba"],
    )
    # oczekiwane liczności zależne od danych fixture — asertuj konkretne komórki
    assert res.cells[(2024, CHARAKTER_OGOLNY_ARTYKUL)] == ...
    assert res.grand_total == ...
    assert res.has_autorzy_dim is False
```

> **Uwaga dla implementera:** projekt renderuje wyniki z widoku
> materializowanego `bpp_rekord_mat`. W testach twórz publikacje istniejącymi
> fabrykami (np. `baker.make("bpp.Wydawnictwo_Ciagle", rok=2024, charakter_formalny=art, punkty_kbn=40)`)
> i odśwież cache tak, jak robią to inne testy multiseek/rekord w
> `src/bpp/tests/` (poszukaj fixture/helpera odświeżającego `Rekord`).
> NIE wymyślaj własnego mechanizmu — użyj istniejącego wzorca projektu.

- [ ] **Step 2: Uruchom — ma paść (brak `zbuduj_pivot`)**

Run: `uv run pytest src/bpp/tests/test_multiseek_pivot.py -k zbuduj_pivot_a_liczba -p no:cacheprovider -q 2>&1 | tee /tmp/pivot_t2.log; tail -5 /tmp/pivot_t2.log`
Expected: FAIL.

- [ ] **Step 3: Zaimplementuj `PivotResult` + `zbuduj_pivot` (strategia A)**

```python
# dopisz do src/bpp/multiseek_registry/pivot.py
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, Sum

BRAK = "— brak —"


@dataclass
class PivotResult:
    rows: list
    cols: list
    cells: dict
    row_totals: dict
    col_totals: dict
    grand_total: object
    row_dim: PivotDimension
    col_dim: PivotDimension | None
    metric: PivotMetric
    has_autorzy_dim: bool


def _annotate(metric):
    return Count("id") if metric.field is None else Sum(metric.field)


def zbuduj_pivot(base_qs, row_dim, col_dim, metric):
    base_qs = base_qs.order_by()  # KRYTYCZNE: bez tego ordering wchodzi do GROUP BY
    has_autorzy = row_dim.autorzy or bool(col_dim and col_dim.autorzy)
    triples = (
        _pairs_strategy(base_qs, row_dim, col_dim, metric)
        if has_autorzy
        else _dedup_strategy(base_qs, row_dim, col_dim, metric)
    )
    return _build_matrix(triples, row_dim, col_dim, metric, has_autorzy)


def _dedup_strategy(base_qs, row_dim, col_dim, metric):
    from bpp.models.cache import Rekord

    deduped = Rekord.objects.filter(pk__in=base_qs.values("pk")).order_by()
    group = [row_dim.expr] + ([col_dim.expr] if col_dim else [])
    rows = deduped.values(*group).annotate(val=_annotate(metric))
    for r in rows:
        rk = r[row_dim.expr]
        ck = r[col_dim.expr] if col_dim else None
        yield rk, ck, r["val"] or 0
```

- [ ] **Step 4: Zaimplementuj `_build_matrix` + mapowanie etykiet**

```python
# dopisz do src/bpp/multiseek_registry/pivot.py
def _build_matrix(triples, row_dim, col_dim, metric, has_autorzy):
    cells, row_totals, col_totals = {}, {}, {}
    row_keys, col_keys, grand = set(), set(), 0
    for rk, ck, val in triples:
        cells[(rk, ck)] = cells.get((rk, ck), 0) + val
        row_totals[rk] = row_totals.get(rk, 0) + val
        col_totals[ck] = col_totals.get(ck, 0) + val
        grand += val
        row_keys.add(rk)
        if col_dim:
            col_keys.add(ck)
    rows = _labels(row_keys, row_dim)
    cols = _labels(col_keys, col_dim) if col_dim else []
    return PivotResult(
        rows=rows, cols=cols, cells=cells, row_totals=row_totals,
        col_totals=col_totals, grand_total=grand, row_dim=row_dim,
        col_dim=col_dim, metric=metric, has_autorzy_dim=has_autorzy,
    )


def _labels(keys, dim):
    """Zwraca posortowaną listę (key, label). Rok/koszyk malejąco liczbowo,
    słowniki alfabetycznie po etykiecie."""
    mapping = _label_mapping(keys, dim)
    pairs = [(k, mapping.get(k, BRAK if k is None else str(k))) for k in keys]
    if dim.key in ("rok", "koszyk_pk"):
        pairs.sort(key=lambda p: (p[0] is None, -(p[0] or 0)))
    else:
        pairs.sort(key=lambda p: (p[1] == BRAK, p[1].lower()))
    return pairs


def _label_mapping(keys, dim):
    if dim.label_kind == "raw":
        return {k: (BRAK if k is None else str(k)) for k in keys}
    if dim.label_kind == "pk_bucket":
        return {
            k: (BRAK if k is None else f"{Decimal(k):g}") for k in keys
        }
    if dim.label_kind == "choices_charakter_ogolny":
        d = dict(CHARAKTER_OGOLNY_CHOICES)
        return {k: (BRAK if k is None else d.get(k, str(k))) for k in keys}
    if dim.label_kind in ("fk", "autor"):
        ids = [k for k in keys if k is not None]
        objs = dim.fk_model.objects.in_bulk(ids)
        out = {None: BRAK}
        for k in ids:
            obj = objs.get(k)
            out[k] = str(obj) if obj is not None else BRAK
        return out
    return {k: str(k) for k in keys}
```

- [ ] **Step 5: Uruchom test strategii A — ma przejść**

Run: `uv run pytest src/bpp/tests/test_multiseek_pivot.py -k zbuduj_pivot_a_liczba -p no:cacheprovider -q 2>&1 | tee /tmp/pivot_t2.log; grep -E "passed|failed|error" /tmp/pivot_t2.log | tail -3`
Expected: PASS.

- [ ] **Step 6: Failing test — K1 (filtr mnożący nie zawyża) i K3 (ordering leak)**

```python
@pytest.mark.django_db
def test_zbuduj_pivot_k1_filtr_mnozacy_nie_zawyza(rekordy_pivot):
    """Rekord z wieloma autorami + filtr po autorach/jednostce (JOIN mnożący)
    liczony po wymiarze REKORDOWYM (rok) = raz, nie N razy."""
    from bpp.multiseek_registry import pivot
    # zbuduj queryset z JOIN do autorzy (np. .filter(autorzy__jednostka=...))
    # tak, by płaski COUNT bez dedup zawyżał; asertuj że pivot liczy rekord raz
    ...


@pytest.mark.django_db
def test_zbuduj_pivot_k3_ordering_nie_rozbija_grup(rekordy_pivot):
    """Wejściowy queryset z .order_by('-rok') / Meta.ordering nie rozbija
    GROUP BY na mikrogrupy — liczba wierszy = liczba unikatowych lat."""
    from bpp.multiseek_registry import pivot

    qs = rekordy_pivot.order_by("-rok", "tytul_oryginalny_sort")
    res = pivot.zbuduj_pivot(
        qs, pivot.DIMENSIONS["rok"], None, pivot.METRICS["liczba"]
    )
    assert len(res.rows) == len({r["rok"] for r in rekordy_pivot.values("rok")})
```

- [ ] **Step 7: Uruchom K1/K3 — strategia A już powinna je spełniać**

Run: `uv run pytest src/bpp/tests/test_multiseek_pivot.py -k "k1_filtr or k3_ordering" -p no:cacheprovider -q 2>&1 | tee /tmp/pivot_t2b.log; grep -E "passed|failed|error" /tmp/pivot_t2b.log | tail -3`
Expected: PASS (dedup przez `pk__in` + `order_by()` już to załatwiają). Jeśli
FAIL — popraw `_dedup_strategy` / czyszczenie orderingu.

- [ ] **Step 8: Failing test — strategia B (K2: 3 autorów z jednej kliniki = 1 praca)**

```python
@pytest.mark.django_db
def test_zbuduj_pivot_b_k2_trzej_autorzy_jedna_klinika(...):
    """Rekord z 3 autorami z tej samej jednostki → komórka = 1 praca,
    Σ punkty = punkty rekordu RAZ (nie ×3)."""
    from bpp.multiseek_registry import pivot
    # utwórz 1 rekord (punkty_kbn=40) z 3 autorami w jednostce J
    # base_qs = Rekord z JOIN autorzy
    res_liczba = pivot.zbuduj_pivot(
        base_qs, pivot.DIMENSIONS["jednostka"], None, pivot.METRICS["liczba"]
    )
    assert res_liczba.cells[(J.pk, None)] == 1
    res_pk = pivot.zbuduj_pivot(
        base_qs, pivot.DIMENSIONS["jednostka"], None, pivot.METRICS["punkty_kbn"]
    )
    assert res_pk.cells[(J.pk, None)] == 40
    assert res_liczba.has_autorzy_dim is True
```

- [ ] **Step 9: Uruchom — ma paść (brak `_pairs_strategy`)**

Run: `uv run pytest src/bpp/tests/test_multiseek_pivot.py -k b_k2_trzej -p no:cacheprovider -q 2>&1 | tee /tmp/pivot_t2c.log; tail -5 /tmp/pivot_t2c.log`
Expected: FAIL (`NameError: _pairs_strategy`).

- [ ] **Step 10: Zaimplementuj `_pairs_strategy` (unikatowe pary + agregacja w Pythonie)**

```python
# dopisz do src/bpp/multiseek_registry/pivot.py
def _pairs_strategy(base_qs, row_dim, col_dim, metric):
    """Wymiar autorski: liczymy pary (wymiar, rekord). Rekord liczony raz per
    wartość wymiaru; Σ metryki po unikatowych parach (rekord, wymiar).
    Dublowanie MIĘDZY różnymi wartościami wymiaru jest zamierzone (§7)."""
    group = [row_dim.expr] + ([col_dim.expr] if col_dim else [])
    fields = group + ["id"] + ([metric.field] if metric.field else [])
    pairs = base_qs.values(*fields).distinct()
    seen = {}   # (rk, ck) -> set(rekord id) dla liczby
    sums = {}   # (rk, ck) -> Σ metryki po unikatowych rekordach
    for p in pairs:
        rk = p[row_dim.expr]
        ck = p[col_dim.expr] if col_dim else None
        rid = tuple(p["id"]) if isinstance(p["id"], list) else p["id"]
        s = seen.setdefault((rk, ck), set())
        if rid in s:
            continue
        s.add(rid)
        if metric.field is None:
            sums[(rk, ck)] = sums.get((rk, ck), 0) + 1
        else:
            sums[(rk, ck)] = sums.get((rk, ck), 0) + (p[metric.field] or 0)
    for (rk, ck), val in sums.items():
        yield rk, ck, val
```

- [ ] **Step 11: Uruchom test K2 — ma przejść**

Run: `uv run pytest src/bpp/tests/test_multiseek_pivot.py -k b_k2_trzej -p no:cacheprovider -q 2>&1 | tee /tmp/pivot_t2c.log; grep -E "passed|failed|error" /tmp/pivot_t2c.log | tail -3`
Expected: PASS.

- [ ] **Step 12: Failing test — NULL-kubły → „— brak —" i koszyk PK**

```python
@pytest.mark.django_db
def test_zbuduj_pivot_null_bucket_i_koszyk_pk(...):
    from bpp.multiseek_registry import pivot
    # rekord z zrodlo=None → etykieta BRAK; punkty_kbn=0 → "0"
    res = pivot.zbuduj_pivot(base_qs, pivot.DIMENSIONS["koszyk_pk"], None,
                             pivot.METRICS["liczba"])
    labels = dict(res.rows)
    assert "0" in labels.values()
```

- [ ] **Step 13: Uruchom cały plik testów jednostkowych pivota**

Run: `uv run pytest src/bpp/tests/test_multiseek_pivot.py -p no:cacheprovider -q 2>&1 | tee /tmp/pivot_t2all.log; grep -E "passed|failed|error" /tmp/pivot_t2all.log | tail -3`
Expected: PASS (wszystkie).

- [ ] **Step 14: ruff + commit**

```bash
uv run ruff format src/bpp/multiseek_registry/pivot.py src/bpp/tests/test_multiseek_pivot.py
uv run ruff check src/bpp/multiseek_registry/pivot.py src/bpp/tests/test_multiseek_pivot.py
git add src/bpp/multiseek_registry/pivot.py src/bpp/tests/test_multiseek_pivot.py
git commit -m "feat(multiseek): zbuduj_pivot — agregacja A/B, etykiety, sumy brzegowe"
```

---

## Task 3: `report_type="pivot"` + wpięcie w widok

**Files:**
- Modify: `src/bpp/multiseek_registry/reports.py:8`
- Modify: `src/bpp/views/mymultiseek.py` (`get_context_data`)
- Test: `src/bpp/tests/test_multiseek_pivot_view.py`

**Interfaces:**
- Consumes: `parse_pivot_params`, `zbuduj_pivot`, `PivotResult` (Task 1-2).
- Produces: kontekst widoku z kluczem `pivot` (`PivotResult`) gdy
  `report_type == "pivot"`; `report_type` string `"pivot"` z rejestru.

- [ ] **Step 1: Dopisz report_type na KOŃCU listy**

```python
# src/bpp/multiseek_registry/reports.py — ostatnia pozycja listy:
    BibTeXReportType("bibtex", "BibTeX"),
    ReportType("pivot", "tabela krzyżowa"),
]
```

- [ ] **Step 2: Failing test — widok z report_type=pivot zwraca kontekst pivota**

```python
# src/bpp/tests/test_multiseek_pivot_view.py
import pytest


@pytest.mark.django_db
def test_pivot_results_view_zwraca_pivot(client, ...):
    """Po ustawieniu formularza z report_type=pivot w sesji, GET na
    /multiseek/results/?pivot_row=rok&pivot_val=liczba renderuje macierz."""
    # ustaw sesję multiseek z report_type wskazującym pivot (indeks ostatni)
    # oraz danymi filtra; wykonaj GET z parametrami pivota
    resp = client.get("/multiseek/results/?pivot_row=rok&pivot_val=liczba")
    assert resp.status_code == 200
    assert "pivot" in resp.context
    assert resp.context["pivot"].row_dim.key == "rok"
```

> **Uwaga:** wzorzec ustawiania sesji multiseek + report_type znajdź w
> istniejących testach (`src/bpp/tests/` / `src/integration_tests/` szukaj
> `multiseek_json` / `results`). report_type = indeks pozycyjny → pivot to
> ostatni indeks listy `multiseek_report_types`.

- [ ] **Step 3: Uruchom — ma paść (brak klucza `pivot`)**

Run: `uv run pytest src/bpp/tests/test_multiseek_pivot_view.py -k zwraca_pivot -p no:cacheprovider -q 2>&1 | tee /tmp/pivot_t3.log; tail -5 /tmp/pivot_t3.log`
Expected: FAIL.

- [ ] **Step 4: Wepnij gałąź pivota w `get_context_data`**

```python
# src/bpp/views/mymultiseek.py — w MyMultiseekResults.get_context_data,
# po ustaleniu ctx["report_type"], PRZED liczeniem agregatów listy:
        if ctx.get("report_type") == "pivot":
            from bpp.multiseek_registry import pivot as pivot_mod

            base_qs = self.get_queryset_for_current_mode()
            row_dim, col_dim, metric = pivot_mod.parse_pivot_params(self.request.GET)
            ctx["pivot"] = pivot_mod.zbuduj_pivot(base_qs, row_dim, col_dim, metric)
            ctx["pivot_dimensions"] = pivot_mod.DIMENSIONS
            ctx["pivot_metrics"] = pivot_mod.METRICS
            ctx["paginator_count"] = 0
            return ctx
        # ... istniejąca logika agregatów listy poniżej
```

> Gałąź pivota **omija** cache agregatów, `qset.count()` i sumy stopki
> (spec §8). Zostaw istniejącą logikę nietkniętą poniżej `return`.

- [ ] **Step 5: Uruchom test widoku — ma przejść**

Run: `uv run pytest src/bpp/tests/test_multiseek_pivot_view.py -k zwraca_pivot -p no:cacheprovider -q 2>&1 | tee /tmp/pivot_t3.log; grep -E "passed|failed|error" /tmp/pivot_t3.log | tail -3`
Expected: PASS.

- [ ] **Step 6: Test stabilności indeksów report_type**

```python
@pytest.mark.django_db
def test_pivot_report_type_na_koncu_listy():
    from bpp.multiseek_registry.reports import multiseek_report_types
    assert multiseek_report_types[-1].id == "pivot"
    assert multiseek_report_types[-1].public is True
    # dotychczasowe typy zachowują pozycje (list/table na 0/1)
    assert multiseek_report_types[0].id == "list"
    assert multiseek_report_types[1].id == "table"
```

- [ ] **Step 7: Uruchom + ruff + commit**

```bash
uv run pytest src/bpp/tests/test_multiseek_pivot_view.py -p no:cacheprovider -q 2>&1 | tee /tmp/pivot_t3all.log; grep -E "passed|failed|error" /tmp/pivot_t3all.log | tail -3
uv run ruff format src/bpp/views/mymultiseek.py src/bpp/multiseek_registry/reports.py src/bpp/tests/test_multiseek_pivot_view.py
uv run ruff check src/bpp/views/mymultiseek.py src/bpp/multiseek_registry/reports.py src/bpp/tests/test_multiseek_pivot_view.py
git add src/bpp/views/mymultiseek.py src/bpp/multiseek_registry/reports.py src/bpp/tests/test_multiseek_pivot_view.py
git commit -m "feat(multiseek): report_type pivot + wpięcie PivotResult w widok"
```

---

## Task 4: Template `report-body-pivot.html` + branch + SCSS

**Files:**
- Create: `src/django_bpp/templates/multiseek/report-body-pivot.html`
- Modify: `src/django_bpp/templates/multiseek/common-results.html:9`
- Modify: SCSS (znajdź plik komponentów multiseek: `grep -rl "multiseek-report-container" src/**/static/**/*.scss`)
- Test: `src/bpp/tests/test_multiseek_pivot_view.py` (asercje HTML)

**Interfaces:**
- Consumes: `ctx["pivot"]` (`PivotResult`), `ctx["pivot_dimensions"]`,
  `ctx["pivot_metrics"]`, `ctx["report_type"]`.

- [ ] **Step 1: Failing test — HTML macierzy renderuje się i zawiera „RAZEM"**

```python
@pytest.mark.django_db
def test_pivot_html_zawiera_macierz_i_razem(client, ...):
    resp = client.get("/multiseek/results/?pivot_row=rok&pivot_val=liczba")
    html = resp.content.decode()
    assert 'class="multiseek-pivot' in html
    assert "RAZEM" in html
```

- [ ] **Step 2: Uruchom — ma paść**

Run: `uv run pytest src/bpp/tests/test_multiseek_pivot_view.py -k html_zawiera -p no:cacheprovider -q 2>&1 | tee /tmp/pivot_t4.log; tail -5 /tmp/pivot_t4.log`
Expected: FAIL.

- [ ] **Step 3: Gałąź pivota w common-results.html (przed gate 25000)**

```django
{# src/django_bpp/templates/multiseek/common-results.html — po otwarciu #}
{# <div class="multiseek-report-container"> (linia 9) wstaw: #}
    {% if report_type == "pivot" %}
        {% include "multiseek/report-body-pivot.html" %}
    {% else %}
    {# ... CAŁA dotychczasowa zawartość od `{% if paginator_count > 25000 %}` ... #}
    {% endif %}
```

> Gałąź pivota jest PRZED `{% if paginator_count > 25000 %}` i przed
> `{% autopaginate %}` — pivot nie fetchuje rekordów listy ani nie
> stronicuje. Zamknij `{% endif %}` przed `</div>` zamykającym kontener
> (linia ~122). Każda linia komentarza `{# #}` osobno (reguła projektu).

- [ ] **Step 4: Utwórz `report-body-pivot.html`**

```django
{# src/django_bpp/templates/multiseek/report-body-pivot.html #}
{% load i18n %}
<form method="get" class="multiseek-pivot-controls" action=".">
    <label>Wiersze
        <select name="pivot_row" onchange="this.form.submit()">
            {% for key, dim in pivot_dimensions.items %}
                <option value="{{ key }}"{% if key == pivot.row_dim.key %} selected{% endif %}>{{ dim.label }}</option>
            {% endfor %}
        </select>
    </label>
    <label>Kolumny
        <select name="pivot_col" onchange="this.form.submit()">
            <option value="">(brak)</option>
            {% for key, dim in pivot_dimensions.items %}
                {% if dim.allow_column %}
                    <option value="{{ key }}"{% if pivot.col_dim and key == pivot.col_dim.key %} selected{% endif %}>{{ dim.label }}</option>
                {% endif %}
            {% endfor %}
        </select>
    </label>
    <label>W komórce
        <select name="pivot_val" onchange="this.form.submit()">
            {% for key, m in pivot_metrics.items %}
                <option value="{{ key }}"{% if key == pivot.metric.key %} selected{% endif %}>{{ m.label }}</option>
            {% endfor %}
        </select>
    </label>
</form>

<div class="multiseek-pivot-scroll">
<table class="multiseek-pivot">
    <thead>
        <tr>
            <th>{{ pivot.row_dim.label }}</th>
            {% for ck, clabel in pivot.cols %}<th>{{ clabel }}</th>{% endfor %}
            <th class="pivot-total">RAZEM</th>
        </tr>
    </thead>
    <tbody>
        {% for rk, rlabel in pivot.rows %}
        <tr>
            <th>{{ rlabel }}</th>
            {% if pivot.cols %}
                {% for ck, clabel in pivot.cols %}
                    <td>{{ pivot.cells|pivot_cell:rk|pivot_cell:ck }}</td>
                {% endfor %}
            {% else %}
                <td>{{ pivot.cells|pivot_cell:rk|pivot_cell:None }}</td>
            {% endif %}
            <td class="pivot-total">{{ pivot.row_totals|dict_get:rk }}</td>
        </tr>
        {% endfor %}
    </tbody>
    <tfoot>
        <tr>
            <th class="pivot-total">RAZEM</th>
            {% for ck, clabel in pivot.cols %}<td class="pivot-total">{{ pivot.col_totals|dict_get:ck }}</td>{% endfor %}
            <td class="pivot-total">{{ pivot.grand_total }}</td>
        </tr>
    </tfoot>
</table>
</div>

{% if pivot.has_autorzy_dim %}
<p class="multiseek-pivot-note">
    ⓘ Grupowanie po jednostce/dyscyplinie/autorze liczy powiązania, nie unikatowe prace —
    praca powiązana z wieloma jednostkami liczona jest w każdej z nich; sumy mogą przewyższać wartości całkowite.
</p>
{% endif %}
```

> **Filtry szablonowe:** Django nie indeksuje krotek/dictów po zmiennym
> kluczu. Dwie opcje (wybierz prostszą dla projektu):
> (a) dołóż mały template-tag/filtr `dict_get` i `pivot_cell` w istniejącej
> bibliotece tagów multiseek (`src/bpp/templatetags/`), LUB
> (b) w `zbuduj_pivot`/widoku przekształć `PivotResult` w gotowe do
> iteracji listy wierszy `[{"label":..., "cells":[...], "total":...}]` +
> nagłówki + stopkę, i renderuj bez indeksowania po kluczu.
> **Rekomendacja: (b)** — czystszy szablon, brak magii filtrów. Jeśli
> wybierzesz (b), dodaj do `PivotResult` metodę/property `as_table()`
> zwracającą tę strukturę i użyj jej w template (zmień test HTML odpowiednio).

- [ ] **Step 5: SCSS — styl tabeli krzyżowej (sticky nagłówki, scroll)**

```scss
// w pliku komponentów multiseek (bez nadpisywania siatki Foundation):
.multiseek-pivot-scroll { overflow-x: auto; }
.multiseek-pivot {
    border-collapse: collapse;
    th, td { border: 1px solid #ccc; padding: 4px 10px; text-align: right; }
    thead th, tbody th { text-align: left; background: #f4f4f4; }
    .pivot-total { font-weight: bold; background: #eee; }
}
.multiseek-pivot-note { color: #666; font-size: 0.85em; margin-top: 0.5em; }
.multiseek-pivot-controls { margin-bottom: 1em; display: flex; gap: 1em; flex-wrap: wrap; }
```

Po zmianie SCSS: `grunt build` (patrz Global Constraints / docs).

- [ ] **Step 6: Uruchom test HTML + build assetów**

Run: `uv run pytest src/bpp/tests/test_multiseek_pivot_view.py -p no:cacheprovider -q 2>&1 | tee /tmp/pivot_t4all.log; grep -E "passed|failed|error" /tmp/pivot_t4all.log | tail -3`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/django_bpp/templates/multiseek/report-body-pivot.html \
        src/django_bpp/templates/multiseek/common-results.html \
        src/bpp/tests/test_multiseek_pivot_view.py
# + zmienione pliki SCSS i zbudowane assety, jeśli dotyczy
git commit -m "feat(multiseek): partial tabeli krzyżowej + branch + styl"
```

---

## Task 5: Eksport pivota (XLSX/CSV) — omija cap 5000

**Files:**
- Modify: `src/bpp/views/mymultiseek.py` (`MyMultiseekExport.get` / `_export_data`)
- Modify: `src/bpp/views/multiseek_export.py` (builder z `PivotResult`)
- Test: `src/bpp/tests/test_multiseek_pivot_view.py`

**Interfaces:**
- Consumes: `parse_pivot_params`, `zbuduj_pivot`, `PivotResult`.
- Produces: `pivot_xlsx_export_response(pivot_result, request, title)` i
  `pivot_csv_export_response(pivot_result, request, title)` w
  `multiseek_export.py`.

- [ ] **Step 1: Failing test — eksport XLSX pivota, cap 5000 nie blokuje**

```python
@pytest.mark.django_db
def test_pivot_export_xlsx_liczby_zgodne_z_widokiem(admin_client, ...):
    # ustaw sesję report_type=pivot; GET eksportu
    resp = admin_client.get("/multiseek/export/xlsx/?pivot_row=rok&pivot_val=liczba")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml"
    )
    # (opcjonalnie) wczytaj openpyxl i porównaj sumę z grand_total
```

- [ ] **Step 2: Uruchom — ma paść (eksport traktuje pivot jak dane listy / cap)**

Run: `uv run pytest src/bpp/tests/test_multiseek_pivot_view.py -k export_xlsx -p no:cacheprovider -q 2>&1 | tee /tmp/pivot_t5.log; tail -5 /tmp/pivot_t5.log`
Expected: FAIL.

- [ ] **Step 3: Gałąź pivota w `MyMultiseekExport.get` (przed cap 5000)**

```python
# src/bpp/views/mymultiseek.py — w MyMultiseekExport.get, na początku,
# PRZED `count = queryset.count()` / cap 5000:
        registry = get_registry(self.registry)
        report_type = registry.get_report_type(
            self.get_multiseek_data(), request=request
        )
        if report_type == "pivot":
            from bpp.multiseek_registry import pivot as pivot_mod
            from bpp.views.multiseek_export import (
                pivot_csv_export_response,
                pivot_xlsx_export_response,
            )

            base_qs = self.get_queryset_for_current_mode()
            row_dim, col_dim, metric = pivot_mod.parse_pivot_params(request.GET)
            pr = pivot_mod.zbuduj_pivot(base_qs, row_dim, col_dim, metric)
            title = _multiseek_report_title(request)
            if export_format == "csv":
                return pivot_csv_export_response(pr, request, title)
            if export_format == "xlsx":
                return pivot_xlsx_export_response(pr, request, title)
            return HttpResponseBadRequest(
                "Eksport tabeli krzyżowej dostępny jako XLSX lub CSV."
            )
```

- [ ] **Step 4: Buildery w `multiseek_export.py`**

```python
# src/bpp/views/multiseek_export.py — nowe funkcje budujące płaską macierz
# (nagłówek: [etykieta wiersza] + etykiety kolumn + "RAZEM"; wiersze danych;
# wiersz RAZEM). Wykorzystaj istniejące helpery XLSX/CSV z tego modułu.
def _pivot_rows(pr):
    header = [pr.row_dim.label] + [c[1] for c in pr.cols] + ["RAZEM"]
    yield header
    for rk, rlabel in pr.rows:
        row = [rlabel]
        if pr.cols:
            row += [pr.cells.get((rk, ck), "") for ck, _ in pr.cols]
        else:
            row += [pr.cells.get((rk, None), "")]
        row.append(pr.row_totals.get(rk, 0))
        yield row
    footer = ["RAZEM"] + [pr.col_totals.get(ck, 0) for ck, _ in pr.cols] + [pr.grand_total]
    yield footer


def pivot_csv_export_response(pr, request, report_title):
    ...  # analogicznie do csv_export_response, ale z _pivot_rows(pr)


def pivot_xlsx_export_response(pr, request, report_title):
    ...  # analogicznie do xlsx_export_response, ale z _pivot_rows(pr)
```

> Wykorzystaj istniejące funkcje `csv_export_response` /
> `xlsx_export_response` jako wzorzec (nagłówki HTTP, nazwa pliku,
> openpyxl). `_pivot_rows` daje wiersze; reszta jak w istniejących.

- [ ] **Step 5: Uruchom test eksportu — ma przejść**

Run: `uv run pytest src/bpp/tests/test_multiseek_pivot_view.py -k export -p no:cacheprovider -q 2>&1 | tee /tmp/pivot_t5.log; grep -E "passed|failed|error" /tmp/pivot_t5.log | tail -3`
Expected: PASS.

- [ ] **Step 6: ruff + commit**

```bash
uv run ruff format src/bpp/views/mymultiseek.py src/bpp/views/multiseek_export.py src/bpp/tests/test_multiseek_pivot_view.py
uv run ruff check src/bpp/views/mymultiseek.py src/bpp/views/multiseek_export.py src/bpp/tests/test_multiseek_pivot_view.py
git add src/bpp/views/mymultiseek.py src/bpp/views/multiseek_export.py src/bpp/tests/test_multiseek_pivot_view.py
git commit -m "feat(multiseek): eksport XLSX/CSV tabeli krzyżowej (omija cap 5000)"
```

---

## Task 6: Ukryj eksport dla anonima + newsfragment + pełny przebieg

**Files:**
- Modify: `src/django_bpp/templates/multiseek/report-body-pivot.html` (przycisk eksportu tylko dla zalogowanych)
- Create: `src/bpp/newsfragments/multiseek-pivot.feature.rst`
- Test: `src/bpp/tests/test_multiseek_pivot_view.py`

- [ ] **Step 1: Dodaj przyciski eksportu (tylko zalogowany) do partiala**

```django
{# w report-body-pivot.html, pod tabelą (nad/pod adnotacją): #}
{% if request.user.is_authenticated %}
<div class="multiseek-pivot-export">
    <a href="../export/xlsx/?{{ request.GET.urlencode }}">⬇️ XLSX</a>
    <a href="../export/csv/?{{ request.GET.urlencode }}">⬇️ CSV</a>
</div>
{% endif %}
```

> Eksport pivota jest `LoginRequiredMixin` — dla anonima link i tak dałby
> redirect do logowania, więc ukrywamy go (spec §9.3).

- [ ] **Step 2: Test — anonim nie widzi eksportu, zalogowany widzi**

```python
@pytest.mark.django_db
def test_pivot_export_ukryty_dla_anonima(client, admin_client, ...):
    anon = client.get("/multiseek/results/?pivot_row=rok").content.decode()
    assert "export/xlsx" not in anon
    logged = admin_client.get("/multiseek/results/?pivot_row=rok").content.decode()
    assert "export/xlsx" in logged
```

- [ ] **Step 3: Newsfragment**

```rst
.. src/bpp/newsfragments/multiseek-pivot.feature.rst
Nowy typ raportu „tabela krzyżowa" w wyszukiwarce: grupowanie wyników
(oraz prac autora) w pivot — wybierany wymiar wierszy i kolumn oraz
metryka w komórce (liczba prac, suma punktów PK, IF, cytowań), z sumami
brzegowymi i eksportem do XLSX/CSV.
```

- [ ] **Step 4: Pełny przebieg testów pivota + powiązanych**

Run: `uv run pytest src/bpp/tests/test_multiseek_pivot.py src/bpp/tests/test_multiseek_pivot_view.py -p no:cacheprovider -q 2>&1 | tee /tmp/pivot_full.log; grep -E "passed|failed|error" /tmp/pivot_full.log | tail -3`
Expected: PASS (wszystkie).

- [ ] **Step 5: Regresja multiseek (istniejące testy nietknięte)**

Run: `uv run pytest src/bpp/tests/ -k multiseek -p no:cacheprovider -q 2>&1 | tee /tmp/pivot_reg.log; grep -E "passed|failed|error" /tmp/pivot_reg.log | tail -3`
Expected: PASS (report_type dopisany na końcu nie rusza istniejących indeksów).

- [ ] **Step 6: Commit**

```bash
git add src/django_bpp/templates/multiseek/report-body-pivot.html \
        src/bpp/newsfragments/multiseek-pivot.feature.rst \
        src/bpp/tests/test_multiseek_pivot_view.py
git commit -m "feat(multiseek): ukryj eksport pivota dla anonima + newsfragment"
```

---

## Self-Review (wypełnione)

**Spec coverage:**
- §4 report_type + GET → Task 3 (report_type), Task 1 (parse GET). ✓
- §5 UI (selektory, RAZEM, scroll, adnotacja pod tabelą, puste komórki) → Task 4. ✓
- §6 menu wymiarów/metryk + mapowanie etykiet → Task 1 (rejestry) + Task 2 (`_label_mapping`). ✓
- §7 semantyka Autorzy (pary, K2, adnotacja) → Task 2 (`_pairs_strategy`), Task 4 (adnotacja). ✓
- §8 strategia A/B, czyszczenie orderingu, brak count/cache → Task 2 + Task 3. ✓
- §9 eksport (cap 5000 bypass, kontrakt DANE/DOKUMENT, LoginRequired) → Task 5 + Task 6. ✓
- §11 testy (K1/K2/K3, NULL, indeksy, degeneracja, eksport, anonim) → rozłożone po Task 2-6. ✓
- Multi-hosted `ukryte_statusy` — dziedziczone z `get_queryset` (Task 3 używa `get_queryset_for_current_mode`), pokryte istniejącą logiką. ✓

**Placeholder scan:** Kod-steps mają realny kod; miejsca oznaczone `...`
to WYŁĄCZNIE dane fixture/asercje zależne od danych testowych oraz dwa
buildery eksportu wzorowane na istniejących funkcjach — z jawną
instrukcją, skąd wziąć wzorzec. Brak „TODO/TBD/handle edge cases".

**Type consistency:** `PivotDimension`/`PivotMetric`/`PivotResult`,
`parse_pivot_params`, `zbuduj_pivot`, `_dedup_strategy`/`_pairs_strategy`/
`_build_matrix`/`_labels`/`_label_mapping`, `_pivot_rows`,
`pivot_{csv,xlsx}_export_response` — nazwy spójne między Task 1-6.

**Znane ryzyko dla implementera (świadome):** fixtury tworzące wpisy w
`bpp_rekord_mat`/`bpp_autorzy_mat` MUSZĄ użyć istniejącego w projekcie
mechanizmu odświeżania cache (Task 2 Step 1 uwaga) — to jedyne miejsce,
gdzie plan celowo odsyła do wzorca projektu zamiast dyktować kod, bo
mechanizm jest projektowo-specyficzny.
