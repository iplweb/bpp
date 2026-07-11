# Eksport Multiseek do HTML i DOCX (+ BibTeX `.bib`) — design

Data: 2026-07-10
Gałąź: `feat-multiseek-eksport-html-docx` (worktree off `dev`)
Rewizja: v2 (po review Fable #1 — poprawki N+1, numeracja, pandoc/docker,
sanityzacja, reuse `export_to_bibtex`)

## 1. Cel

Rozszerzyć dropdown eksportu wyników Multiseek o trzy nowe formaty **eksportu
dokumentu**, odwzorowujące to, co user faktycznie widzi na ekranie
(`common-results.html`):

- **HTML** — samodzielny plik `.html` z aktualnym renderem (lista opisów /
  tabela punktacyjna),
- **DOCX** — ten sam render skonwertowany do Worda,
- **BibTeX (`.bib`)** — gdy aktualny `report_type == "bibtex"`, surowy plik
  `.bib` zamiast HTML/DOCX.

Istniejące eksporty **danych** (CSV, XLS:dane, XLS:opis) pozostają bez zmian.

## 2. Kontekst i stan obecny

- Route: `^multiseek/export/(?P<export_format>[\w-]+)/$` →
  `bpp.views.mymultiseek.MyMultiseekExport` (`src/django_bpp/urls.py:308`).
  Regexp `[\w-]+` już przyjmuje nowe formaty — **bez zmian w `urls.py`**.
- `MyMultiseekExport(LoginRequiredMixin, MyMultiseekResults).get()`
  (`src/bpp/views/mymultiseek.py`): waliduje format ∈ `{csv, xlsx}`, czyta
  `?wariant=` ∈ `{dane, opis}`, sprawdza limit `MULTISEEK_EXPORT_MAX_ROWS`
  (5000), zawęża queryset, woła buildery z `bpp/views/multiseek_export.py`.
- `MyMultiseekResults.get_queryset()` (`mymultiseek.py:58-107`) stosuje
  `.only()` **dostrojony do renderu ekranowego, nie do eksportu**:
  - list/numer_list/None → `flds = ("id", "opis_bibliograficzny_cache")`,
  - EXTRA_TYPES (tabele) → dokłada `charakter_formalny, typ_kbn, punkty_kbn,
    impact_factor, adnotacje, uwagi, punktacja_wewnetrzna,
    charakter_formalny__nazwa, typ_kbn__nazwa`.
  **UWAGA (znalezione w review):** ten zestaw **nie zawiera `liczba_cytowan`**
  (renderowanej w tabelach `_cytowania`, `common-results.html:200`) ani
  `uwagi` dla `numer_list` (renderowanej w liście, `common-results.html:132`).
  Na ekranie (≤25/stronę) to latentny N+1; przy eksporcie **całego** querysetu
  (do 5000) byłoby do 5000 dodatkowych zapytań. Dlatego eksport dokumentu
  **nie polega** na projekcji bazowej — patrz D9/§4.4.
- Buildery `csv_export_response` / `xlsx_export_response`
  (`src/bpp/views/multiseek_export.py`) budują **własne kolumny** z querysetu.
- Render ekranowy: `templates/multiseek/common-results.html` renderuje treść
  zależnie od `report_type`:
  - `bibtex` → `<pre>` z `element.original.to_bibtex`,
  - `list`/`numer_list`/`None` → numerowany `<ol>` z `opis_bibliograficzny_cache`
    (+ `uwagi` dla `numer_list`),
  - warianty tabelaryczne (`table`, `pkt_wewn`, `pkt_wewn_bez`, każdy też
    `_cytowania`) → `<table>` z kolumnami zależnymi od `report_type` + stopka
    `Suma:` (tylko na ostatniej stronie).
- **Reuse DOCX:** `src/nowe_raporty/docx_export.py::html_to_docx(html) -> bytes`
  — najpierw `pypandoc`, przy `(OSError|RuntimeError)` fallback na dockerowy
  `iplweb/html2docx`. `DocxConversionError` gdy oba padną. `nh3.clean` jest
  używane w siostrzanym `as_docx()`, ale **`html_to_docx()` samo nie
  sanityzuje** — sanityzacja po naszej stronie (D8).
- **Reuse BibTeX:** `bpp/export/bibtex.py::export_to_bibtex(publications) -> str`
  (do potwierdzenia sygnatura przy implementacji) — gotowa konkatenacja.

## 3. Kluczowe decyzje projektowe

| # | Decyzja | Uzasadnienie |
|---|---------|--------------|
| D1 | Dwie rozłączne rodziny: eksport **danych** (CSV/XLSX, stałe kolumny) vs eksport **dokumentu** (HTML/DOCX/BibTeX, wg `report_type`). | Odmienna semantyka; HTML/DOCX renderują prezentację, nie kolumny — nie pasują do modelu `wariant=`. |
| D2 | HTML/DOCX **wiernie odwzorowują aktualny `report_type`** (lista lub tabela). | Wybór usera: „biorą to, co się renderuje w multiseeku". |
| D3 | `report_type == "bibtex"` → eksport jako `.bib` (nie HTML/DOCX). | BibTeX jest tekstowy; `.bib` to kanoniczne rozszerzenie, MIME `application/x-bibtex`. |
| D4 | **Wydzielić wspólne partiale** z `common-results.html`; render ekranowy i eksport dzielą jedno źródło markupu. | Zero rozjazdu kolumn tabeli przy przyszłych zmianach. |
| D5 | DOCX przez istniejący `html_to_docx()`. Realnie: **pandoc jest ścieżką pierwszą i produkcyjną** (binarka zapieczona w obrazie, `docker/bpp_base/Dockerfile`), a **dockerowy `html2docx` to rescue na twardej awarii** (brak binarki → OSError, non-zero exit → RuntimeError). Na instalacjach, gdzie „pandoc nie działa" i pada w sposób podnoszący wyjątek, fallback dockera to pokrywa. | Reuse przetestowanego kodu; nie pogarszamy zachowania. Znane ograniczenie: pandoc obecny, ale cicho generujący zły plik (exit 0) **nie** wyzwoli fallbacku — poza zakresem v1 (współdzielony kod z `nowe_raporty`), patrz §10. |
| D6 | Wspólny limit **5000** (`MULTISEEK_EXPORT_MAX_ROWS`) także dla HTML/DOCX/BibTeX. | Spójność z CSV/XLSX; ogranicza koszt konwersji dokumentu. Decyzja rewidowalna. |
| D7 | W dokumencie: tylko tytuł tekstowy (bez logo/grafik), bez linków `<a>` wokół opisu (relatywne URL-e psują pobrany plik), bez przycisków „usuń". | YAGNI; czysty, przenośny dokument. |
| D8 | **Sanityzacja** treści dokumentu przez `nh3.clean` (allowlist rozszerzony o tagi strukturalne `ol/li/table/...`) przed odpowiedzią `.html` i przed `html_to_docx`. | Plik opuszcza serwis (brak CSP, `file://`, re-hosting); DB-sourced HTML z `opis_bibliograficzny_cache` musi być czyszczony — spójnie z siostrzanym `as_docx()` i z sanityzacją CSV/XLSX. |
| D9 | Eksport dokumentu stosuje **własną projekcję** `.only()`/`select_related` dostrojoną do renderowanego partiala (nie reużywa projekcji bazowej z `get_queryset()`). | Bazowa projekcja gubi `liczba_cytowan`/`uwagi` → N+1 na 5000 rekordach (blocker z review). Nie ruszamy projekcji ekranowej (ryzyko dla `test_mymultiseek_query_count.py`). |

## 4. Architektura

### 4.1 Wydzielenie partiali (refaktor `common-results.html`)

Nowe include'y w `src/django_bpp/templates/multiseek/`:

- `report-body-list.html` — numerowany `<ol>` opisów (+ `uwagi` dla numer_list).
- `report-body-table.html` — tabela punktacyjna (kolumny wg `report_type`) +
  opcjonalna stopka `Suma:`.
- `report-body-bibtex.html` — `<pre>` z `to_bibtex` (używany tylko na ekranie;
  eksport BibTeX omija HTML).

Każdy partial **musi mieć własny `{% load i18n %}`** (i inne potrzebne tag-liby
— `{% trans %}`, `{% url %}`, `prace`) — biblioteki tagów **nie** dziedziczą się
przez `{% include %}`.

Parametry include'a (`{% include ... with %}`):

- `export_mode` (bool, default `False`) — gdy `True`: chowa przyciski
  „❌ usuń" i opuszcza `<a>`-link wokół opisu (czysty tekst; relatywne
  `{% url %}` psuje pobrany plik). **Gate przycisku usuwania musi brzmieć
  `{% if not export_mode and not print_removed %}`** — nie sam
  `not print_removed`. Powód (review #2): w kontekście eksportu `print_removed`
  jest nieustawione (falsy), więc branch by się wyrenderował; `nh3.clean`
  usunie `<a data-remove-result>`, ale **zostawi tekst „❌"** jako węzeł
  tekstowy. Gate na `export_mode` jest więc wymagany dla poprawności, nie
  kosmetyki.
- `start_index` (int, **0-based offset**, default `0`) — **jednolita semantyka
  w obu partialach**:
  - lista: `counter-reset: list-counter {{ start_index }}`,
  - tabela: `{{ start_index|add:forloop.counter }}` (pierwszy wiersz = 1).
  Ekran przekazuje `page_obj.start_index|add:-1` do **obu**; eksport przekazuje
  `0` do obu. (Naprawia off-by-one z review — bez tego eksport tabeli
  numerowałby od „0".)
- Stopka `Suma:` (tabela) — **NIE** przez parametr `show_footer` z `{% include
  with %}`: Django `token_kwargs` przyjmuje tylko wyrażenia filtrowe, **nie
  operator `==`**, więc `show_footer=page_obj.number == …` to TemplateSyntaxError
  (blocker z review #2). Zamiast tego warunek **wewnątrz partiala**, z gate na
  `export_mode` jako pierwszym członie (żeby nie dotknąć `page_obj` w eksporcie,
  gdzie jest nieustawiony):
  `{% if export_mode or page_obj.number == page_obj.paginator.num_pages %}`
  wokół `<tfoot>`. Eksport (`export_mode=True`) zawsze pokazuje sumę; ekran —
  jak dotąd, tylko na ostatniej stronie.

`common-results.html` po refaktorze zawiera partiale z `export_mode=False`
i dotychczasowym `start_index`, zachowując render on-screen **bez zmian**
(regression gate: `test_mymultiseek.py`, `test_mymultiseek_query_count.py`).
Refaktor mechaniczny: przeniesienie markupu 1:1 + parametryzacja numeracji/chrome.

### 4.2 Szablon dokumentu eksportu (shell + wstrzyknięty body)

Nowy `src/django_bpp/templates/multiseek/export-document.html` = **zaufana
skorupa**:

- pełny `<!doctype html>` + `<meta charset="utf-8">`,
- `<title>` i `<h1>` = tytuł raportu z sesji (`_multiseek_report_title`),
- minimalny inline CSS — **selektory elementowe** (`table, td, th { border… }`),
  NIE klasy: `nh3.clean` usuwa atrybuty `class`/`style` z wstrzykniętego body,
  więc stylowanie po klasach nie zadziała (review #2). Natywne `<ol>` w eksporcie
  (bez paginacji) i tak numeruje 1..N poprawnie bez `counter-reset`.
- `{{ report_title }}` w `<title>`/`<h1>` **bez `|safe`** — autoescaping. Powód
  (review #2): `plain_multiseek_report_title` robi `html.unescape` **po**
  `strip_tags`, więc tytuł może zawierać literalny `<`; `|safe` byłoby XSS.
- `{{ body_html|safe }}` — **już zsanityzowany** fragment (patrz §4.3).

Skorupa jest w pełni pod naszą kontrolą (nie zawiera DB-content poza
`report_title`, renderowanym z autoescapingiem), więc `|safe` na `body_html`
jest bezpieczne **dopiero po** `nh3.clean`.

### 4.3 Buildery i render (`bpp/views/multiseek_export.py`)

Krok renderu (w widoku — potrzebny `request`):
1. `body_html = render_to_string("multiseek/report-body-<list|table>.html",
   ctx, request=request)` (ctx: `object_list`, `report_type`, `sumy`,
   `export_mode=True`, `start_index=0`, `show_footer=True`),
2. `clean_body = sanitize_export_html(body_html)` — `nh3.clean` z allowlistą
   będącą **unią** (nie podzbiorem — review #2) `set(DEFAULT_ALLOWED_TAGS)`
   z `docx_export.py` (zawiera m.in. `h4, strike, font`, ważne bo markup opisu
   pochodzi z per-instalacyjnych, DB-konfigurowalnych szablonów) i tagów
   strukturalnych: `{table, thead, tbody, tfoot, tr, td, th, ol, ul, li, p,
   div, span, h1, h2, h3, br, hr, pre, code}`. Atrybuty: `td/th → colspan`
   (`class`/`style` celowo odrzucone).
3. `document_html = render_to_string("multiseek/export-document.html",
   {"body_html": clean_body, "report_title": report_title}, request)`.

Nowe funkcje builderów:

- `html_export_response(document_html, report_title) -> HttpResponse`
  — `text/html; charset=utf-8`, załącznik `eksport-<tytuł>.html`
  (reuse `_export_filename("html", ...)`).
- `docx_export_response(document_html, report_title) -> HttpResponse`
  — import lokalny `from nowe_raporty.docx_export import html_to_docx`
  (jak `xlsx_export_response` importuje openpyxl lokalnie), zwraca
  `application/vnd.openxmlformats-officedocument.wordprocessingml.document`,
  załącznik `.docx`. `DocxConversionError` **propaguje** (500) — nie tłumimy.
- `bibtex_export_response(queryset, report_title) -> HttpResponse`
  — **reuse** `bpp.export.bibtex.export_to_bibtex((r.original for r in
  queryset.iterator(chunk_size=1000)))` (sygnaturę potwierdzić przy
  implementacji); `application/x-bibtex; charset=utf-8`, załącznik
  `eksport-<tytuł>.bib`.
- `sanitize_export_html(html) -> str` — helper `nh3.clean` z allowlistą wyżej.

### 4.4 Widok `MyMultiseekExport.get` (+ projekcja eksportowa)

```
DATA_FORMATS = {"csv", "xlsx"}
DOCUMENT_FORMATS = {"html", "docx", "bib"}

# projekcje dostrojone do renderu (naprawiają N+1 z review):
MULTISEEK_RENDER_LIST_FIELDS = ("id", "opis_bibliograficzny_cache", "uwagi")
MULTISEEK_RENDER_TABLE_FIELDS = (
    "id", "opis_bibliograficzny_cache", "impact_factor", "punkty_kbn",
    "liczba_cytowan", "punktacja_wewnetrzna",
    "charakter_formalny", "typ_kbn",
    "charakter_formalny__nazwa", "typ_kbn__nazwa",
)
TABLE_REPORT_TYPES = set(EXTRA_TYPES)  # pkt_wewn*, table* (+ _cytowania)
```

Rozgałęzienie na starcie:

- format ∉ (DATA_FORMATS ∪ DOCUMENT_FORMATS) → `HttpResponseBadRequest`.
- Wspólnie: limit 5000 (`queryset.count()`), `LoginRequiredMixin`.
- **csv/xlsx**: istniejąca ścieżka bez zmian.
- **html/docx/bib** (eksport dokumentu):
  - `queryset = self.get_queryset_for_current_mode()` (report_type-aware
    filtrowanie/status/distinct z bazy),
  - `report_type = registry.get_report_type(self.get_multiseek_data(),
    request=self.request)`,
  - **bibtex-view** (`report_type == "bibtex"`):
    - `bib` → `bibtex_export_response(queryset, report_title)`,
    - `html`/`docx` (nie występują w dropdownie tego widoku, ale gdyby ktoś
      trafił URL-em) → degradacja do `.bib`; **nazwa pliku i MIME wg realnego
      formatu `bib`** (nie `export_format`),
  - **inne widoki** (lista/tabela):
    - `bib` → `HttpResponseBadRequest` („BibTeX dostępny tylko w widoku BibTeX"),
    - jeśli `report_type in TABLE_REPORT_TYPES`:
      - `queryset = queryset.select_related("charakter_formalny", "typ_kbn")
        .only(*MULTISEEK_RENDER_TABLE_FIELDS)`,
      - `sumy = queryset.aggregate(Sum("impact_factor"), Sum("liczba_cytowan"),
        Sum("punkty_kbn"), Sum("punktacja_wewnetrzna"))` (klucze `*__sum`
        zgodne z `report-body-table.html`; agregat liczony **przed** iteracją
        renderu — osobne zapytanie, ale bez N+1),
      - partial = `report-body-table.html`,
    - w innym razie (list/numer_list/None):
      - `queryset = queryset.only(*MULTISEEK_RENDER_LIST_FIELDS)`,
      - `sumy = None`, partial = `report-body-list.html`,
    - render (§4.3 kroki 1-3) → `html`/`docx` builder.

Uwaga: ponowne `.only()` na querysecie z `get_queryset()` **zastępuje** zestaw
pól bazowych (semantyka Django), zachowując `select_related`/`distinct`
z bazy. URL bez zmian (`[\w-]+`). Filenames generyczne (`_export_filename`).

### 4.5 Adaptacyjny dropdown (`templates/multiseek/paginator.html`)

`report_type` jest w kontekście include'a (dziedziczone przez `{% include ...
with %}` bez `only`; już używane w `common-results.html:103`). Nowe pozycje
**wewnątrz istniejącego `dropdown-pane`** (`paginator.html:53`), którego id/toggle
są już zdezambiguowane sufiksem `magellan` (top/bottom) — dzięki temu podwójny
include (górny+dolny) nie łamie unikalności id.

Zawartość:
- CSV / XLS:dane / XLS:opis — zawsze (bez zmian),
- `report_type == "bibtex"` → **„BibTeX (.bib)"** (`{% url "multiseek-export"
  "bib" %}`),
- w każdym innym widoku → **„HTML"** (`... "html"`) + **„DOCX (Word)"**
  (`... "docx"`).

Zachowany wzorzec `print_removed` w query-stringu.

## 5. Przepływ danych

```
user klika [Eksport ▸ HTML|DOCX|BibTeX]
  → GET /multiseek/export/<fmt>/[?print-removed=1]
  → MyMultiseekExport.get(fmt)
     ├─ walidacja fmt, limit 5000, login
     ├─ queryset = get_queryset_for_current_mode()
     ├─ report_type = registry.get_report_type(...)
     ├─ bibtex-view → bibtex_export_response → .bib (export_to_bibtex)
     └─ inaczej:
          ├─ tabela? → .only(TABLE_FIELDS)+select_related, sumy=aggregate
          │  inaczej → .only(LIST_FIELDS), sumy=None
          ├─ body = render_to_string("report-body-<list|table>", ctx, request)
          ├─ clean = sanitize_export_html(body)          # nh3.clean (D8)
          ├─ doc = render_to_string("export-document.html", {body_html: clean})
          ├─ fmt == html → html_export_response(doc) → .html
          └─ fmt == docx → docx_export_response(doc)
                            → html_to_docx() [pandoc→docker html2docx] → .docx
```

## 6. Obsługa błędów

- Nieznany format / `bib` poza widokiem bibtex / >5000 rekordów →
  `HttpResponseBadRequest` (spójne z obecnym `csv/xlsx`).
- Anonim → redirect na login (`LoginRequiredMixin`, bez zmian).
- `DocxConversionError` (pandoc i docker padły) → propaguje jako 500; NIE
  tłumimy po cichu (reguła projektu o wyjątkach; logowanie już w
  `docx_export.py`).
- Sanityzacja (D8) `nh3.clean` biegnie na body PRZED odpowiedzią `.html`
  i przed `html_to_docx`.

## 7. Testy (TDD)

Pliki: rozszerzenie `src/bpp/tests/test_views/test_mymultiseek.py`,
`src/bpp/tests/test_views/test_mymultiseek_query_count.py`, ewentualny nowy
`test_multiseek_export_document.py`.

**Buildery/helper (unit):**
- `html_export_response`: Content-Type `text/html`, Content-Disposition
  `attachment; filename="eksport-*.html"`, treść zawiera markup listy/tabeli.
- `docx_export_response`: monkeypatch `html_to_docx` → sentinel bytes (wzorzec
  z `nowe_raporty/tests/test_docx_export.py`); Content-Type docx, `.docx`.
  Dodatkowo **jeden** realny przebieg (pandoc lokalnie) → nagłówek ZIP
  `PK\x03\x04`. Test fallbacku: monkeypatch `pypandoc.convert_text` → `OSError`,
  monkeypatch `_convert_using_docker_image` → sentinel; assert docker-branch użyty.
- `bibtex_export_response`: Content-Type `application/x-bibtex`, `.bib`, treść
  zawiera `@` wpisy.
- `sanitize_export_html`: `<script>`/on-atrybuty usunięte; `<i>/<sub>/<sup>`
  w opisie zachowane; `<table>/<ol>/<li>` zachowane.

**Routing widoku (integration, `@pytest.mark.django_db`):**
- każdy format (`html`, `docx`, `bib`) → 200 + poprawny Content-Type;
- `report_type` → właściwy render: list vs table (`<ol>` vs `<table>`
  + kolumny wg wariantu tabeli), parametryzacja po `list`, `numer_list`,
  `table`, `pkt_wewn`, `pkt_wewn_cytowania`, `table_cytowania`;
- **numeracja tabeli**: pierwszy wiersz eksportu = „1." (regression off-by-one);
- **stopka tabeli**: eksport zawiera `<tfoot>` z `Suma:` (bo `export_mode`),
  niezależnie od paginacji; ekran — bez zmian (tylko ostatnia strona);
- **tytuł z `<`**: title sesji `<b>x` → w eksporcie zescape'owany (`&lt;b&gt;`),
  nie surowy tag;
- **numer_list**: render zawiera `uwagi`;
- widok bibtex: endpoint `bib` → `.bib`; `html`/`docx` degradują do `.bib`
  (nazwa `*.bib`);
- `bib` w widoku nie-bibtex → 400;
- >5000 rekordów → 400 (mock count);
- `?print-removed=1` eksport dokumentu → 200, render tylko usuniętych;
- anon → redirect; nieznany format → 400.

**Query-count (regression N+1, guard dla D9):**
- eksport `table_cytowania` (z `liczba_cytowan`) i `numer_list` (z `uwagi`) na
  N rekordach → liczba zapytań **stała** (nie rośnie z N); wzorzec
  z `test_mymultiseek_query_count.py`. To złapałoby blocker z review.
- eksport ekranowy (partial extraction) — istniejące query-count testy bez zmian.

**Regresja partiali:**
- istniejące testy renderu ekranowego przechodzą bez zmian (dowód, że
  wydzielenie partiali nie zmieniło on-screen output).

**Uruchomienie lokalnie:** `make tests-without-playwright` +
`uv run pytest src/bpp/tests/test_views/test_mymultiseek*.py`.

## 8. Pliki (create/modify)

**Modify:**
- `src/bpp/views/mymultiseek.py` — rozgałęzienie `get()`, ścieżka dokumentu,
  projekcje `MULTISEEK_RENDER_*`, liczenie `sumy`, `render_to_string`.
- `src/bpp/views/multiseek_export.py` — `html_export_response`,
  `docx_export_response`, `bibtex_export_response`, `sanitize_export_html`
  (import `nh3`).
- `src/django_bpp/templates/multiseek/common-results.html` — zamiana inline
  markupu listy/tabeli/bibtex na `{% include %}` partiali.
- `src/django_bpp/templates/multiseek/paginator.html` — adaptacyjny dropdown.

**Create:**
- `src/django_bpp/templates/multiseek/report-body-list.html`
- `src/django_bpp/templates/multiseek/report-body-table.html`
- `src/django_bpp/templates/multiseek/report-body-bibtex.html`
- `src/django_bpp/templates/multiseek/export-document.html`
- newsfragment towncrier (`changes/`), testy.

**Bez zmian:** `src/django_bpp/urls.py` (regexp już pasuje).

## 9. Świadome uproszczenia (YAGNI)

- Brak logo/grafik w dokumencie (tylko tytuł tekstowy).
- Brak `wariant=` dla HTML/DOCX.
- Limit 5000 wspólny (rewidowalny, D6).
- BibTeX tylko w widoku bibtex (nie generujemy `.bib` z dowolnego widoku).

## 10. Ryzyka

- **Wydzielenie partiali** dotyka gorącego widoku ekranowego — mitigacja:
  istniejące testy renderu + query-count jako regression gate; refaktor
  mechaniczny (markup 1:1 + parametry numeracji).
- **Pandoc „cicho" zły (exit 0, zły plik)** nie wyzwoli fallbacku dockera
  (`html_to_docx` łapie tylko wyjątki, brak walidacji outputu pandoca) —
  współdzielone z `nowe_raporty`, poza zakresem v1; udokumentowane (D5).
- **DOCX/BibTeX na 5000 wierszach** — koszt czasu (pandoc/docker; `to_bibtex`
  = 1 pełny obiekt + autorzy per rekord). Ograniczone limitem 5000, `iterator()`
  tnie pamięć. Akceptowalne w v1.
