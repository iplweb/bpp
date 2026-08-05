# Multiseek XLSX — dwa warianty eksportu — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dodać drugi wariant eksportu XLSX wyników multiseeka („opis
bibliograficzny" w jednej kolumnie) i wzbogacić istniejący eksport kolumnowy
o kolumny Źródło + Typ MNiSW/MEiN — realizacja Freshdesk #373.

**Architecture:** Wydzielamy logikę eksportu z `bpp/views/mymultiseek.py` do
nowego modułu `bpp/views/multiseek_export.py` (commit bez zmiany zachowania),
potem dokładamy dwie kolumny do wariantu `dane` i nowy wariant `opis`
wybierany query-paramem `?wariant=`, a UI dostaje dropdown Foundation
w paginatorze. Kluczowe ryzyko — N+1 przy do 5000 wierszy — adresujemy
per-wariant `select_related` + `only('…__nazwa')` i pilnujemy testem
query-count.

**Tech Stack:** Django, openpyxl, multiseek, Foundation (frontend), pytest +
model_bakery.

## Global Constraints

- Python `uv run` prefix dla WSZYSTKICH komend Pythona (`uv run pytest …`).
- Max długość linii: 88 znaków (ruff).
- NIE modyfikować istniejących migracji; tu migracji nie ma (wszystkie pola
  już istnieją na `Rekord`).
- Django template comments `{# … #}` — każda linia własne `{# … #}`.
- Ikony frontendu publicznego: Foundation-Icons (`<i class="fi-…">`), nie emoji.
- Eksport ograniczony do `MULTISEEK_EXPORT_MAX_ROWS = 5000` (bez zmian).
- Sanityzacja formuł XLSX/CSV (`=`, `+`, `-`, `@`, Tab/CR/LF) — zachować.
- Spec źródłowy: `docs/superpowers/specs/2026-07-08-multiseek-xlsx-warianty-eksportu-design.md`.

---

## File Structure

- **Create** `src/bpp/views/multiseek_export.py` — cała logika serializacji
  eksportu: stałe nagłówków/pól, helpery tekstowe/URL, dwa iteratory wierszy,
  dwa buildery odpowiedzi. Jedna odpowiedzialność: „zamień queryset Rekordów
  na plik CSV/XLSX".
- **Modify** `src/bpp/views/mymultiseek.py` — usunąć przeniesioną logikę,
  importować z nowego modułu; `MyMultiseekExport.get` zyskuje odczyt `wariant`.
- **Modify** `src/django_bpp/templates/multiseek/paginator.html` — dwa linki
  (CSV, XLS) → dropdown „Eksport ▾" z trzema pozycjami.
- **Modify** `src/bpp/tests/test_views/test_mymultiseek.py` — przepisać
  hardkodowane asercje układu XLSX; dodać testy nowych kolumn, wariantu `opis`,
  degradacji CSV, nieznanego wariantu, query-count, `print-removed`+`wariant`.
- **Create** `src/bpp/newsfragments/fd373.feature.rst` — nota wydaniowa.

---

### Task 1: Refactor — wydzielenie logiki eksportu (bez zmiany zachowania)

Czysto mechaniczne przeniesienie. Zero zmian w kolumnach, formatach, routingu.
Cel: `git`-owy diff kolejnych tasków pokazuje logikę, nie „szum przenoszenia".
Istniejące testy `test_mymultiseek.py` muszą przejść bez modyfikacji.

**Files:**
- Create: `src/bpp/views/multiseek_export.py`
- Modify: `src/bpp/views/mymultiseek.py` (usuń przeniesione symbole, dodaj import)
- Test: `src/bpp/tests/test_views/test_mymultiseek.py` (bez zmian — regresja)

**Interfaces:**
- Produces (publiczna powierzchnia nowego modułu, używana przez widok):
  - `MULTISEEK_EXPORT_MAX_ROWS: int` — zostaje w widoku (używa go
    `get_context_data`); NIE przenosić.
  - `csv_export_response(queryset, request, report_title: str) -> HttpResponse`
  - `xlsx_export_response(queryset, request, report_title: str, wariant: str) -> HttpResponse`
    — w Tasku 1 sygnatura jeszcze bez `wariant` (dodany w Tasku 3); na razie
    `xlsx_export_response(queryset, request, report_title) -> HttpResponse`.
  - `plain_multiseek_report_title(value) -> str` (był `_plain_multiseek_report_title`)
  - `MULTISEEK_DEFAULT_REPORT_TITLE: str`
  - `MULTISEEK_EXPORT_DANE_FIELDS: tuple[str, ...]` (był `MULTISEEK_EXPORT_FIELDS`)

**Przenoszone symbole (verbatim, BEZ modyfikacji treści) z `mymultiseek.py`:**
stałe `MULTISEEK_EXPORT_HEADERS`, `MULTISEEK_EXPORT_XLSX_HEADERS`,
`MULTISEEK_EXPORT_XLSX_URL_COLUMNS`, `EXPORT_FILENAME_INVALID_CHARS_RE`,
`MULTISEEK_REPORT_TITLE_HTML_BREAK_RE`, `XLSX_WORKSHEET_TITLE_INVALID_CHARS_RE`,
`SPREADSHEET_FORMULA_INJECTION_LEAD`, `XLSX_WORKSHEET_TITLE_MAX_LENGTH`,
`MULTISEEK_DEFAULT_REPORT_TITLE`; funkcje `_export_value`, `_single_line_text`,
`_plain_multiseek_report_title`→`plain_multiseek_report_title`,
`_export_filename`, `_xlsx_worksheet_title`, `_sanitize_spreadsheet_cell`,
`_sanitize_spreadsheet_row`, `_pbn_publication_url`, `_admin_change_url`,
`_iter_export_rows`, `_csv_export_response`→`csv_export_response`,
`_xlsx_export_response`→`xlsx_export_response`. Zmienić `MULTISEEK_EXPORT_FIELDS`
→ `MULTISEEK_EXPORT_DANE_FIELDS` (nazwa pod przyszły drugi zestaw).

**Zostaje w `mymultiseek.py`:** `MULTISEEK_REPORT_TITLE_SESSION_KEY`,
`MULTISEEK_EXPORT_MAX_ROWS`, `_multiseek_report_title` (czyta sesję; woła
`plain_multiseek_report_title` z modułu), klasy widoków.

- [ ] **Step 1: Utwórz `multiseek_export.py` z przeniesioną treścią**

Utwórz `src/bpp/views/multiseek_export.py`. Nagłówek modułu + importy:

```python
"""Serializacja wyników Multiseek do plików eksportu (CSV / XLSX).

Wydzielone z bpp/views/mymultiseek.py — widok trzyma routing i stan sesji,
ten moduł zamienia queryset Rekordów na gotową odpowiedź HTTP z plikiem.
"""

import csv
import html
import io
import re

from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.http import content_disposition_header

from bpp import const
from bpp.models import Uczelnia
```

Następnie **przenieś verbatim** wszystkie stałe i funkcje wymienione wyżej
(z `mymultiseek.py`, obecne linie 40-93 dla stałych oraz 235-397 dla
funkcji), zmieniając tylko:
- `MULTISEEK_EXPORT_FIELDS` → `MULTISEEK_EXPORT_DANE_FIELDS`,
- `_plain_multiseek_report_title` → `plain_multiseek_report_title` (public),
- `_csv_export_response` → `csv_export_response` (public),
- `_xlsx_export_response` → `xlsx_export_response` (public).

Wewnętrzne wywołania między przeniesionymi funkcjami zaktualizuj do nowych
nazw. `_iter_export_rows` zostaje prywatne (na razie).

- [ ] **Step 2: Zaktualizuj `mymultiseek.py` — usuń przeniesione, dodaj import**

Usuń z `mymultiseek.py` przeniesione stałe i funkcje. Zostaw
`MULTISEEK_REPORT_TITLE_SESSION_KEY = "MULTISEEK_TITLE"`,
`MULTISEEK_EXPORT_MAX_ROWS = 5000`, oraz `_multiseek_report_title`. Dodaj import:

```python
from bpp.views.multiseek_export import (
    MULTISEEK_DEFAULT_REPORT_TITLE,
    csv_export_response,
    plain_multiseek_report_title,
    xlsx_export_response,
)
```

Zaktualizuj `_multiseek_report_title`, by wołało `plain_multiseek_report_title`:

```python
def _multiseek_report_title(request):
    return plain_multiseek_report_title(
        request.session.get(
            MULTISEEK_REPORT_TITLE_SESSION_KEY,
            MULTISEEK_DEFAULT_REPORT_TITLE,
        )
    )
```

W `MyMultiseekExport.get` podmień wołania na publiczne nazwy z modułu:

```python
        report_title = _multiseek_report_title(request)
        queryset = queryset.select_related(None).only(*MULTISEEK_EXPORT_DANE_FIELDS)
        if export_format == "csv":
            return csv_export_response(queryset, request, report_title)
        return xlsx_export_response(queryset, request, report_title)
```

Dodaj import `MULTISEEK_EXPORT_DANE_FIELDS` do listy powyżej.

- [ ] **Step 3: Uruchom istniejące testy eksportu — regresja**

Run: `uv run pytest src/bpp/tests/test_views/test_mymultiseek.py -q`
Expected: PASS (ta sama liczba testów co przed refactorem; zero zmian zachowania).

- [ ] **Step 4: Sprawdź brak innych importów starych symboli**

Run: `grep -rn "_csv_export_response\|_xlsx_export_response\|MULTISEEK_EXPORT_FIELDS\|_plain_multiseek_report_title" src/ --include=*.py`
Expected: brak trafień poza definicjami w `multiseek_export.py` (i ich
publicznymi odpowiednikami). Jeśli coś jeszcze importowało stare nazwy — popraw.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/views/multiseek_export.py src/bpp/views/mymultiseek.py
git commit -m "refactor(multiseek): wydziel logikę eksportu do multiseek_export.py

Bez zmiany zachowania — przeniesienie stałych, helperów, iteratora wierszy
i builderów odpowiedzi. Przygotowanie pod drugi wariant eksportu (FD#373)."
```

---

### Task 2: Wariant `dane` — dodaj kolumny Źródło + Typ MNiSW/MEiN

Czysta insercja: `Źródło` po `Autorzy` (kol. 3), `Typ MNiSW/MEiN` po
`Typ rekordu` (kol. 9). `BPP ID` zostaje przed `Typ rekordu`. Dotyczy CSV i XLSX.
Naprawiamy N+1 (per-wariant `select_related`/`only`) i przestajemy hardkodować
indeksy kolumn-linków / formatów liczb (liczymy z nagłówków).

**Files:**
- Modify: `src/bpp/views/multiseek_export.py`
- Modify: `src/bpp/views/mymultiseek.py` (queryset dla wariantu `dane`)
- Test: `src/bpp/tests/test_views/test_mymultiseek.py`

**Interfaces:**
- Consumes: `MULTISEEK_EXPORT_XLSX_HEADERS`, `_iter_export_rows`,
  `xlsx_export_response`, `MULTISEEK_EXPORT_DANE_FIELDS` (z Taska 1).
- Produces: `MULTISEEK_EXPORT_DANE_FIELDS` rozszerzone o `zrodlo__nazwa`,
  `typ_kbn__nazwa`; helper `_xlsx_column_index(headers, predicate) -> list[int]`
  (1-based) do wyliczania kolumn linków/liczb.

- [ ] **Step 1: Napisz failing testy nowych kolumn (CSV + XLSX)**

Dodaj do `test_mymultiseek.py` (dostosuj fixtures do istniejących w pliku —
użyj `baker.make("bpp.Wydawnictwo_Ciagle", ...)` ze źródłem i typem KBN,
zaloguj usera jak w istniejących testach eksportu):

```python
def test_export_dane_csv_ma_zrodlo_i_typ_mnisw(admin_client, wydawnictwo_ciagle):
    resp = admin_client.get("/multiseek/export/csv/")
    assert resp.status_code == 200
    text = resp.content.decode("utf-8")
    header = text.splitlines()[0]
    cols = header.split(",")
    assert cols[2] == "zrodlo"
    assert cols[8] == "typ_mnisw_mein"
    assert cols[6] == "bpp_id"  # BPP ID nadal przed typ_rekordu (kol. 8)
    assert cols[7] == "typ_rekordu"


def test_export_dane_xlsx_ma_zrodlo_i_typ_mnisw(admin_client, wydawnictwo_ciagle):
    from openpyxl import load_workbook

    resp = admin_client.get("/multiseek/export/xlsx/")
    assert resp.status_code == 200
    wb = load_workbook(io.BytesIO(resp.content))
    ws = wb.active
    headers = [c.value for c in ws[1]]
    assert headers[2] == "Źródło"
    assert headers[8] == "Typ MNiSW/MEiN"
    assert headers[6] == "BPP ID"
    assert headers[7] == "Typ rekordu"
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/bpp/tests/test_views/test_mymultiseek.py -k "zrodlo_i_typ" -q`
Expected: FAIL (kolumny nie istnieją / zła kolejność).

- [ ] **Step 3: Rozszerz nagłówki i pola w `multiseek_export.py`**

Podmień stałe na wersje z insercją (dwie nowe kolumny):

```python
MULTISEEK_EXPORT_HEADERS = (
    "tytul_oryginalny",
    "autorzy",
    "zrodlo",
    "rok",
    "impact_factor",
    "pk",
    "bpp_id",
    "typ_rekordu",
    "typ_mnisw_mein",
    "id_rekordu",
    "pbn_uid_id",
    "link_do_bpp_url",
    "link_do_bpp_admin_url",
    "link_do_pbn_url",
)

MULTISEEK_EXPORT_XLSX_HEADERS = (
    "Tytuł oryginalny",
    "Autorzy",
    "Źródło",
    "Rok",
    "Impact Factor",
    "PK",
    "BPP ID",
    "Typ rekordu",
    "Typ MNiSW/MEiN",
    "ID rekordu",
    "PBN UID",
    "Link do BPP",
    "Link do edycji w BPP",
    "Link do PBN",
)

MULTISEEK_EXPORT_DANE_FIELDS = (
    "id",
    "tytul_oryginalny",
    "opis_bibliograficzny_zapisani_autorzy_cache",
    "zrodlo__nazwa",
    "rok",
    "impact_factor",
    "punkty_kbn",
    "typ_kbn__nazwa",
    "pbn_uid_id",
)
```

Usuń stałą `MULTISEEK_EXPORT_XLSX_URL_COLUMNS` (zastąpi ją wyliczanie z nazw).

- [ ] **Step 4: Wstaw wartości Źródło + Typ MNiSW/MEiN w `_iter_export_rows`**

`Zrodlo`/`Typ_KBN` mogą być `None` → pusty string. Używamy `zrodlo.nazwa`
(NIE `str(zrodlo)` — patrz spec §2). Zaktualizuj `_iter_export_rows`:

```python
def _iter_export_rows(queryset, request):
    uczelnia = Uczelnia.objects.get_for_request(request)
    pbn_api_root = uczelnia.pbn_api_root if uczelnia is not None else ""

    for rekord in queryset.iterator(chunk_size=1000):
        zrodlo = rekord.zrodlo
        typ_kbn = rekord.typ_kbn
        yield (
            rekord.tytul_oryginalny,
            rekord.opis_bibliograficzny_zapisani_autorzy_cache,
            zrodlo.nazwa if zrodlo is not None else "",
            rekord.rok,
            rekord.impact_factor,
            rekord.punkty_kbn,
            str(tuple(rekord.pk)),
            str(rekord.describe_content_type),
            typ_kbn.nazwa if typ_kbn is not None else "",
            rekord.object_id,
            _export_value(rekord.pbn_uid_id),
            request.build_absolute_uri(rekord.get_absolute_url()),
            _admin_change_url(rekord, request),
            _pbn_publication_url(rekord.pbn_uid_id, pbn_api_root),
        )
```

- [ ] **Step 5: Wylicz indeksy kolumn z nagłówków (koniec hardkodowania)**

Dodaj helper i użyj go w `xlsx_export_response`:

```python
def _xlsx_columns_where(headers, predicate):
    """1-based indeksy kolumn XLSX, których nagłówek spełnia predykat."""
    return [i for i, h in enumerate(headers, start=1) if predicate(h)]
```

W `xlsx_export_response` zastąp hardkodowane `(10, 11, 12)` oraz kolumny
`min_col=4, max_col=5` (IF/PK) wyliczeniem z `MULTISEEK_EXPORT_XLSX_HEADERS`:

```python
    headers = MULTISEEK_EXPORT_XLSX_HEADERS
    url_cols = _xlsx_columns_where(headers, lambda h: h.startswith("Link"))
    if_cols = _xlsx_columns_where(headers, lambda h: h == "Impact Factor")
    pk_cols = _xlsx_columns_where(headers, lambda h: h == "PK")

    for row in worksheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    for col in if_cols:
        for row in worksheet.iter_rows(min_row=2, min_col=col, max_col=col):
            row[0].number_format = "0.000"
    for col in pk_cols:
        for row in worksheet.iter_rows(min_row=2, min_col=col, max_col=col):
            row[0].number_format = "0.00"

    for row_idx in range(2, worksheet.max_row + 1):
        for col_idx in url_cols:
            cell = worksheet.cell(row=row_idx, column=col_idx)
            if cell.value:
                cell.value = f'=HYPERLINK("{cell.value}", "[link]")'
```

(Reszta `xlsx_export_response` — nagłówek fill/font, `freeze_panes="B1"`,
autosize, tabela — bez zmian.)

- [ ] **Step 6: Napraw N+1 — `select_related` dla wariantu `dane` w widoku**

W `mymultiseek.py`, `MyMultiseekExport.get`, zamień linię budującą queryset
eksportu tak, by po zdjęciu `select_related(None)` przywrócić potrzebne relacje:

```python
        queryset = (
            queryset.select_related(None)
            .select_related("zrodlo", "typ_kbn")
            .only(*MULTISEEK_EXPORT_DANE_FIELDS)
        )
```

- [ ] **Step 7: Przepisz stare hardkodowane asercje układu XLSX**

W `test_mymultiseek.py` istniejące asercje (`worksheet["D2"].number_format ==
"0.000"`, `["E2"] == "0.00"`, pozycje `=HYPERLINK`) są teraz przesunięte o dwie
kolumny: IF→E, PK→F, linki→L/M/N. Zaktualizuj je:

```python
    assert ws["E2"].number_format == "0.000"  # Impact Factor (było D)
    assert ws["F2"].number_format == "0.00"   # PK (było E)
    # kolumny linków (L, M, N) zawierają =HYPERLINK
    for col in ("L", "M", "N"):
        assert ws[f"{col}2"].value.startswith("=HYPERLINK(")
```

(Jeśli konkretny test asertuje wartości danych po indeksie krotki — przesuń
indeksy: źródło wchodzi na pozycję 2 (0-based), typ MNiSW na pozycję 8.)

- [ ] **Step 8: Test query-count dla `dane` (strażnik N+1)**

```python
def test_export_dane_xlsx_nie_ma_n_plus_1(admin_client, django_assert_max_num_queries):
    from openpyxl import load_workbook

    # dwa rekordy o RÓŻNYCH źródłach i typach — gdyby był N+1,
    # liczba zapytań rosłaby z liczbą wierszy
    baker.make("bpp.Wydawnictwo_Ciagle", _quantity=3)
    with django_assert_max_num_queries(15):
        resp = admin_client.get("/multiseek/export/xlsx/")
    assert resp.status_code == 200
    load_workbook(io.BytesIO(resp.content))
```

(Dobierz próg do realnej liczby zapytań zmierzonej lokalnie — ma być STAŁY
względem liczby wierszy; jeśli 15 jest za ciasne/luźne, ustaw wartość tuż nad
zmierzoną. Kluczowe: dodanie kolejnych rekordów NIE zwiększa liczby zapytań.)

- [ ] **Step 9: Uruchom testy**

Run: `uv run pytest src/bpp/tests/test_views/test_mymultiseek.py -q`
Expected: PASS (nowe + przepisane).

- [ ] **Step 10: Commit**

```bash
git add src/bpp/views/multiseek_export.py src/bpp/views/mymultiseek.py \
        src/bpp/tests/test_views/test_mymultiseek.py
git commit -m "feat(multiseek): kolumny Źródło + Typ MNiSW/MEiN w eksporcie (FD#373)

Czysta insercja dwóch kolumn (CSV i XLSX), indeksy kolumn liczone z nagłówków
zamiast hardkodowanych, per-wariant select_related+only przeciw N+1."
```

---

### Task 3: Wariant `opis` (XLSX-only) + routing `?wariant=`

Nowy układ: Lp. | Opis bibliograficzny | IF | PK | Charakter | Typ MNiSW/MEiN.
Opis w jednej komórce (HTML → czysty tekst). Wybór query-paramem.

**Files:**
- Modify: `src/bpp/views/multiseek_export.py`
- Modify: `src/bpp/views/mymultiseek.py` (routing + queryset opis)
- Test: `src/bpp/tests/test_views/test_mymultiseek.py`

**Interfaces:**
- Consumes: `MULTISEEK_REPORT_TITLE_HTML_BREAK_RE`, `_single_line_text`,
  `sanitize_xlsx_row`, `xlsx_export_response` (z Tasków 1-2).
- Produces:
  - `MULTISEEK_EXPORT_OPIS_XLSX_HEADERS: tuple[str, ...]`
  - `MULTISEEK_EXPORT_OPIS_FIELDS: tuple[str, ...]`
  - `_plain_opis_bibliograficzny(value) -> str`
  - `_iter_export_rows_opis(queryset, request) -> Iterator[tuple]`
  - `xlsx_export_response(queryset, request, report_title, wariant="dane")`
    — rozszerzona sygnatura.

- [ ] **Step 1: Napisz failing testy wariantu `opis`**

```python
def test_export_opis_xlsx_uklad(admin_client, wydawnictwo_ciagle):
    from openpyxl import load_workbook

    resp = admin_client.get("/multiseek/export/xlsx/?wariant=opis")
    assert resp.status_code == 200
    wb = load_workbook(io.BytesIO(resp.content))
    ws = wb.active
    headers = [c.value for c in ws[1]]
    assert headers == [
        "Lp.", "Opis bibliograficzny", "IF", "PK", "Charakter", "Typ MNiSW/MEiN",
    ]
    assert ws["A2"].value == 1  # numeracja Lp.


def test_export_opis_czysci_html(admin_client):
    from openpyxl import load_workbook

    baker.make(
        "bpp.Wydawnictwo_Ciagle",
        opis_bibliograficzny_cache="Tytuł <i>Źródła</i> 2026<br>s. 1-2",
    )
    resp = admin_client.get("/multiseek/export/xlsx/?wariant=opis")
    wb = load_workbook(io.BytesIO(resp.content))
    opis = wb.active["B2"].value
    assert "<" not in opis and ">" not in opis
    assert "Źródła" in opis
    assert "  " not in opis  # spacje skolapsowane, <br> nie sklejone


def test_export_opis_csv_degraduje_do_dane(admin_client, wydawnictwo_ciagle):
    resp = admin_client.get("/multiseek/export/csv/?wariant=opis")
    assert resp.status_code == 200
    header = resp.content.decode("utf-8").splitlines()[0]
    assert header.split(",")[0] == "tytul_oryginalny"  # układ dane, nie opis


def test_export_nieznany_wariant_to_dane(admin_client, wydawnictwo_ciagle):
    from openpyxl import load_workbook

    resp = admin_client.get("/multiseek/export/xlsx/?wariant=cokolwiek")
    assert resp.status_code == 200
    ws = load_workbook(io.BytesIO(resp.content)).active
    assert ws[1][0].value == "Tytuł oryginalny"  # układ dane
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/bpp/tests/test_views/test_mymultiseek.py -k "opis or nieznany_wariant" -q`
Expected: FAIL.

- [ ] **Step 3: Dodaj stałe wariantu `opis`**

```python
MULTISEEK_EXPORT_OPIS_XLSX_HEADERS = (
    "Lp.",
    "Opis bibliograficzny",
    "IF",
    "PK",
    "Charakter",
    "Typ MNiSW/MEiN",
)

MULTISEEK_EXPORT_OPIS_FIELDS = (
    "id",
    "opis_bibliograficzny_cache",
    "impact_factor",
    "punkty_kbn",
    "charakter_formalny__nazwa",
    "typ_kbn__nazwa",
)
```

- [ ] **Step 4: Dodaj helper `_plain_opis_bibliograficzny`**

```python
def _plain_opis_bibliograficzny(value):
    """opis_bibliograficzny_cache (HTML) -> jednoliniowy czysty tekst.

    Bez fallbacku na tytuł domyślny (w przeciwieństwie do
    plain_multiseek_report_title): puste wejście -> "". Sanityzacja formuł
    dzieje się później, w sanitize_xlsx_row — tu jej NIE wołamy.
    """
    if not value:
        return ""
    value = MULTISEEK_REPORT_TITLE_HTML_BREAK_RE.sub(" ", value)
    value = html.unescape(strip_tags(value))
    return _single_line_text(value)
```

- [ ] **Step 5: Dodaj iterator wierszy `opis`**

```python
def _iter_export_rows_opis(queryset, request):
    for lp, rekord in enumerate(queryset.iterator(chunk_size=1000), start=1):
        charakter = rekord.charakter_formalny
        typ_kbn = rekord.typ_kbn
        yield (
            lp,
            _plain_opis_bibliograficzny(rekord.opis_bibliograficzny_cache),
            rekord.impact_factor,
            rekord.punkty_kbn,
            charakter.nazwa if charakter is not None else "",
            typ_kbn.nazwa if typ_kbn is not None else "",
        )
```

- [ ] **Step 6: Rozgałęź `xlsx_export_response` per wariant**

Zmień sygnaturę na `xlsx_export_response(queryset, request, report_title,
wariant="dane")`. Na początku wybierz nagłówki + iterator:

```python
    if wariant == "opis":
        headers = MULTISEEK_EXPORT_OPIS_XLSX_HEADERS
        rows = _iter_export_rows_opis(queryset, request)
        freeze = "A2"
    else:
        headers = MULTISEEK_EXPORT_XLSX_HEADERS
        rows = _iter_export_rows(queryset, request)
        freeze = "B1"
```

Użyj `headers` przy `worksheet.append(headers)` i przy wyliczaniu
`url_cols`/`if_cols`/`pk_cols` (Task 2, Step 5). Dla `opis` `url_cols` wyjdzie
puste (brak kolumn „Link…") — pętla HYPERLINK nic nie zrobi, i słusznie.
Ustaw `worksheet.freeze_panes = freeze`. Reszta (fill/font nagłówka, autosize,
tabela, `worksheet.append(sanitize_xlsx_row(row)) for row in rows`) — wspólna.

- [ ] **Step 7: Routing + queryset per wariant w widoku**

W `mymultiseek.py`, `MyMultiseekExport.get`:

```python
    def get(self, request, export_format, *args, **kwargs):
        if export_format not in {"csv", "xlsx"}:
            return HttpResponseBadRequest("Nieznany format eksportu.")

        wariant = request.GET.get("wariant", "dane")
        if wariant not in {"dane", "opis"}:
            wariant = "dane"
        # opis to format czytelny (raportowy) — CSV opisu nie robimy
        if export_format == "csv":
            wariant = "dane"

        queryset = self.get_queryset_for_current_mode()
        count = queryset.count()
        if count > MULTISEEK_EXPORT_MAX_ROWS:
            return HttpResponseBadRequest(
                "Eksport Multiseek jest dostępny dla maksymalnie "
                f"{MULTISEEK_EXPORT_MAX_ROWS} rekordów."
            )

        report_title = _multiseek_report_title(request)
        if wariant == "opis":
            queryset = (
                queryset.select_related(None)
                .select_related("charakter_formalny", "typ_kbn")
                .only(*MULTISEEK_EXPORT_OPIS_FIELDS)
            )
            return xlsx_export_response(queryset, request, report_title, "opis")

        queryset = (
            queryset.select_related(None)
            .select_related("zrodlo", "typ_kbn")
            .only(*MULTISEEK_EXPORT_DANE_FIELDS)
        )
        if export_format == "csv":
            return csv_export_response(queryset, request, report_title)
        return xlsx_export_response(queryset, request, report_title, "dane")
```

Dodaj `MULTISEEK_EXPORT_OPIS_FIELDS` do importu z `multiseek_export`.

- [ ] **Step 8: Test query-count dla `opis`**

```python
def test_export_opis_nie_ma_n_plus_1(admin_client, django_assert_max_num_queries):
    from openpyxl import load_workbook

    baker.make("bpp.Wydawnictwo_Ciagle", _quantity=3)
    with django_assert_max_num_queries(15):
        resp = admin_client.get("/multiseek/export/xlsx/?wariant=opis")
    assert resp.status_code == 200
    load_workbook(io.BytesIO(resp.content))
```

(Próg jak w Task 2 Step 8 — stały względem liczby wierszy.)

- [ ] **Step 9: Uruchom testy**

Run: `uv run pytest src/bpp/tests/test_views/test_mymultiseek.py -q`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add src/bpp/views/multiseek_export.py src/bpp/views/mymultiseek.py \
        src/bpp/tests/test_views/test_mymultiseek.py
git commit -m "feat(multiseek): wariant eksportu 'opis bibliograficzny' XLSX (FD#373)

Nowy układ (opis w jednej kolumnie + IF/PK/Charakter/Typ MNiSW/MEiN) wybierany
?wariant=opis; CSV degraduje do 'dane'; helper czyszczący HTML bez fallbacku;
select_related+only przeciw N+1 z testem query-count."
```

---

### Task 4: UI — dropdown „Eksport ▾" w paginatorze

Dwa linki (CSV, XLS) → jeden trigger + dropdown-pane z trzema pozycjami.
Najpierw weryfikacja dostępności Foundation Dropdown JS.

**Files:**
- Modify: `src/django_bpp/templates/multiseek/paginator.html`

**Interfaces:** brak (czysto szablon). Linki statyczne — patrz Task 3 routing.

- [ ] **Step 1: Zweryfikuj Foundation Dropdown JS na stronie multiseeka**

Run: `grep -rn "data-dropdown\|Foundation.Dropdown\|dropdown-pane" src/django_bpp/templates/ src/bpp/static/ src/django_bpp/static_root* 2>/dev/null | head`
Oraz sprawdź, czy layout multiseeka inicjuje Foundation (`$(document).foundation()`
lub odpowiednik). Jeśli `dropdown-pane` jest już używany gdzieś w publicznym
frontendzie — użyj go (Step 2a). Jeśli NIE ma pewności — użyj natywnego
`<details>` (Step 2b, zero JS). Decyzja binarna, udokumentuj w commicie.

- [ ] **Step 2a: Wariant Foundation dropdown-pane (jeśli JS dostępny)**

W `paginator.html` zastąp blok linii ~32-45 (dwa `<li>` CSV/XLS):

```django
{% if request.user.is_authenticated and paginator_count > 0 and paginator_count <= multiseek_export_max_rows %}
    {% url "multiseek-export" "csv" as ex_csv %}
    {% url "multiseek-export" "xlsx" as ex_xlsx %}
    <li>
        <a data-toggle="multiseek-export-menu"><i class="fi-download"></i> Eksport <span aria-hidden="true">▾</span></a>
    </li>
    <div class="dropdown-pane" id="multiseek-export-menu" data-dropdown data-auto-focus="true">
        <ul class="menu vertical" style="margin-bottom:0;">
            <li><a href="{{ ex_csv }}{% if print_removed %}?print-removed=1{% endif %}"><i class="fi-download"></i> CSV</a></li>
            <li><a href="{{ ex_xlsx }}{% if print_removed %}?print-removed=1{% endif %}"><i class="fi-download"></i> XLS: dane</a></li>
            <li><a href="{{ ex_xlsx }}?wariant=opis{% if print_removed %}&print-removed=1{% endif %}"><i class="fi-download"></i> XLS: opis bibliograficzny</a></li>
        </ul>
    </div>
{% endif %}
```

- [ ] **Step 2b: Wariant natywny `<details>` (jeśli brak pewności co do JS)**

```django
{% if request.user.is_authenticated and paginator_count > 0 and paginator_count <= multiseek_export_max_rows %}
    {% url "multiseek-export" "csv" as ex_csv %}
    {% url "multiseek-export" "xlsx" as ex_xlsx %}
    <li>
        <details class="multiseek-export-details">
            <summary><i class="fi-download"></i> Eksport ▾</summary>
            <ul class="menu vertical" style="margin:0;">
                <li><a href="{{ ex_csv }}{% if print_removed %}?print-removed=1{% endif %}"><i class="fi-download"></i> CSV</a></li>
                <li><a href="{{ ex_xlsx }}{% if print_removed %}?print-removed=1{% endif %}"><i class="fi-download"></i> XLS: dane</a></li>
                <li><a href="{{ ex_xlsx }}?wariant=opis{% if print_removed %}&print-removed=1{% endif %}"><i class="fi-download"></i> XLS: opis bibliograficzny</a></li>
            </ul>
        </details>
    </li>
{% endif %}
```

- [ ] **Step 3: Weryfikacja wizualna (run-site)**

Uruchom stack i obejrzyj paginator wyników multiseeka:

Run: `uv run run-site run --no-browser` (w tle), potem otwórz `/multiseek/results/`
zalogowany (snippet z CLAUDE.md „Autologin"). Sprawdź: dropdown otwiera się,
trzy linki działają, wiersz akcji krótszy niż wcześniej.
Expected: trzy pozycje pobierają odpowiednio CSV / XLS dane / XLS opis.

- [ ] **Step 4: Commit**

```bash
git add src/django_bpp/templates/multiseek/paginator.html
git commit -m "feat(multiseek): dropdown eksportu w paginatorze (FD#373)

Dwa linki (CSV, XLS) zastąpione jednym triggerem 'Eksport ▾' z trzema
pozycjami (CSV, XLS: dane, XLS: opis bibliograficzny) — wiersz akcji krótszy."
```

---

### Task 5: Newsfragment

**Files:**
- Create: `src/bpp/newsfragments/fd373.feature.rst`

- [ ] **Step 1: Utwórz newsfragment**

```rst
Eksport wyników wyszukiwania (multiseek) do XLSX zyskał kolumny „Źródło" oraz
„Typ MNiSW/MEiN", a także drugi wariant, w którym cały opis bibliograficzny
jest w jednej kolumnie (obok IF, PK, Charakter, Typ MNiSW/MEiN). Wybór wariantu
odbywa się z rozwijanego przycisku „Eksport" nad listą wyników (FD#373).
```

- [ ] **Step 2: Commit**

```bash
git add src/bpp/newsfragments/fd373.feature.rst
git commit -m "docs(newsfragment): eksport multiseek — kolumny i wariant opisu (FD#373)"
```

---

## Full-suite validation (po wszystkich taskach)

- [ ] Run: `uv run pytest src/bpp/tests/test_views/test_mymultiseek.py -q` → PASS
- [ ] Run: `ruff format src/bpp/views/multiseek_export.py src/bpp/views/mymultiseek.py`
- [ ] Run: `ruff check src/bpp/views/multiseek_export.py src/bpp/views/mymultiseek.py` → czysto
- [ ] Run: `uv run pytest src/bpp/tests/test_views/ -q` (szerszy regres) → PASS

---

## Self-Review (autor planu)

**Spec coverage:**
- §2 dane (Źródło + Typ MNiSW/MEiN, czysta insercja, CSV+XLSX) → Task 2 ✓
- §2 opis (6 kolumn, helper bez fallbacku, HTML→tekst) → Task 3 ✓
- §3 routing `?wariant=`, degradacja CSV, nieznany→dane → Task 3 Step 7 ✓
- §4 refactor do multiseek_export.py → Task 1 ✓
- §4 select_related/only per wariant (N+1) → Task 2 Step 6, Task 3 Step 7 ✓
- §4 indeksy z nagłówków (startswith „Link", 1-based) → Task 2 Step 5 ✓
- §4 freeze_panes A2 (opis) / B1 (dane) → Task 3 Step 6 ✓
- §5 dropdown UI + fallback `<details>` + print-removed w query → Task 4 ✓
- §6 testy: nowe kolumny, opis, degradacja CSV, nieznany wariant, query-count,
  print-removed → Task 2/3 (uwaga: test print-removed+wariant dopisać w Task 3
  Step 1, patrz niżej) ✓
- §6 przepisanie starych asercji XLSX → Task 2 Step 7 ✓
- §7 newsfragment → Task 5 ✓

**Luka wykryta w self-review:** spec §6 test 6 (`print-removed` + `wariant`
współistnieją) nie ma własnego kroku. Dopisać do Task 3 jako dodatkowy test:

```python
def test_export_print_removed_z_wariantem(admin_client, wydawnictwo_ciagle):
    resp = admin_client.get("/multiseek/export/xlsx/?wariant=opis&print-removed=1")
    assert resp.status_code == 200
```

**Placeholder scan:** brak „TBD/TODO"; progi query-count świadomie kalibrowane
lokalnie (opisane, nie placeholder).

**Type consistency:** `xlsx_export_response(... , wariant="dane")` — sygnatura
spójna między Task 1 (bez `wariant`), Task 3 (dodaje `wariant`); Task 1 celowo
tworzy wersję bez parametru, Task 3 ją rozszerza (zgodne, nie kolizja). Nazwy
`MULTISEEK_EXPORT_DANE_FIELDS` / `MULTISEEK_EXPORT_OPIS_FIELDS` spójne w Task
1/2/3. Helpery `_iter_export_rows` (dane) vs `_iter_export_rows_opis` (opis) —
rozróżnialne.
