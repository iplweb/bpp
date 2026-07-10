# Eksport Multiseek do HTML i DOCX (+ BibTeX `.bib`) — design

Data: 2026-07-10
Gałąź: `feat-multiseek-eksport-html-docx` (worktree off `dev`)

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
  `bpp.views.mymultiseek.MyMultiseekExport` (`src/django_bpp/urls.py`).
  Regexp `[\w-]+` już przyjmuje nowe formaty — **bez zmian w `urls.py`**.
- `MyMultiseekExport(LoginRequiredMixin, MyMultiseekResults).get()`
  (`src/bpp/views/mymultiseek.py`): waliduje format ∈ `{csv, xlsx}`, czyta
  `?wariant=` ∈ `{dane, opis}`, sprawdza limit `MULTISEEK_EXPORT_MAX_ROWS`
  (5000), zawęża queryset (`.only(MULTISEEK_EXPORT_DANE_FIELDS/OPIS_FIELDS)`),
  woła buildery z `bpp/views/multiseek_export.py`.
- Buildery `csv_export_response` / `xlsx_export_response`
  (`src/bpp/views/multiseek_export.py`) budują **własne kolumny** z querysetu —
  niezależnie od `report_type`.
- Render ekranowy: `templates/multiseek/common-results.html` renderuje treść
  zależnie od `report_type`:
  - `bibtex` → `<pre>` z `element.original.to_bibtex`,
  - `list` / `numer_list` / `None` → numerowany `<ol>` z
    `opis_bibliograficzny_cache`,
  - warianty tabelaryczne (`table`, `pkt_wewn`, `pkt_wewn_bez`, każdy też
    `_cytowania`) → `<table>` z kolumnami zależnymi od `report_type` + stopka
    `Suma:`.
  Markup przemieszany z UI (przyciski „❌ usuń", paginator, panele) gated
  `hide-for-print`.
- **Reuse DOCX:** `src/nowe_raporty/docx_export.py::html_to_docx(html) -> bytes`
  konwertuje HTML→DOCX: najpierw `pypandoc`, przy błędzie fallback na
  dockerowy `iplweb/html2docx` (`_convert_using_docker_image`). Post-processing
  page-breaków przez `python-docx`.

## 3. Kluczowe decyzje projektowe

| # | Decyzja | Uzasadnienie |
|---|---------|--------------|
| D1 | Dwie rozłączne rodziny: eksport **danych** (CSV/XLSX, stałe kolumny) vs eksport **dokumentu** (HTML/DOCX/BibTeX, wg `report_type`). | Odmienna semantyka; HTML/DOCX renderują prezentację, nie kolumny — nie pasują do modelu `wariant=`. |
| D2 | HTML/DOCX **wiernie odwzorowują aktualny `report_type`** (lista lub tabela). | Wybór usera: „biorą to, co się renderuje w multiseeku". |
| D3 | `report_type == "bibtex"` → eksport jako `.bib` (nie HTML/DOCX). | BibTeX jest tekstowy; `.bib` to kanoniczne rozszerzenie, MIME `application/x-bibtex`. |
| D4 | **Wydzielić wspólne partiale** z `common-results.html`; render ekranowy i eksport dzielą jedno źródło markupu. | Zero rozjazdu kolumn tabeli przy przyszłych zmianach. |
| D5 | DOCX przez istniejący `html_to_docx()`; **produkcyjny konwerter to dockerowy `html2docx`**, pandoc jest best-effort (na części instalacji nie działa i nie możemy tego zmienić — fallback dockera to pokrywa). | Reuse przetestowanego kodu; niezawodna ścieżka bez pandoca. |
| D6 | Wspólny limit **5000** (`MULTISEEK_EXPORT_MAX_ROWS`) także dla HTML/DOCX/BibTeX. | Spójność z CTV/XLSX; ogranicza koszt konwersji dokumentu. Decyzja rewidowalna. |
| D7 | W dokumencie: tylko tytuł tekstowy (bez logo/grafik), bez linków `<a>` wokół opisu (relatywne URL-e psują pobrany plik), bez przycisków „usuń". | YAGNI; czysty, przenośny dokument. |

## 4. Architektura

### 4.1 Wydzielenie partiali (refaktor `common-results.html`)

Nowe include'y w `src/django_bpp/templates/multiseek/`:

- `report-body-list.html` — numerowany `<ol>` opisów.
- `report-body-table.html` — tabela punktacyjna (kolumny wg `report_type`) +
  opcjonalna stopka `Suma:`.
- `report-body-bibtex.html` — `<pre>` z `to_bibtex` (używany tylko na ekranie;
  eksport BibTeX omija HTML).

Parametry include'a (przekazywane przez `{% include ... with %}`):

- `export_mode` (bool, default `False`) — gdy `True`: chowa przyciski
  „❌ usuń", opuszcza `<a>`-link wokół opisu (czysty tekst).
- `start_index` (int, default `0`) — offset numeracji. Ekran przekazuje
  `page_obj.start_index|add:-1` (lista, `counter-reset`) /
  `page_obj.start_index` (tabela); eksport `0`.
- `show_footer` (bool) — tabela: ekran pokazuje stopkę tylko na ostatniej
  stronie (`page_obj.number == page_obj.paginator.num_pages`), eksport zawsze.

`common-results.html` po refaktorze zawiera partiale z `export_mode=False`,
zachowując render on-screen **bez zmian** (weryfikacja: istniejące
`test_mymultiseek.py`).

### 4.2 Szablon dokumentu eksportu

Nowy `src/django_bpp/templates/multiseek/export-document.html`:

- pełny `<!doctype html>` + `<meta charset="utf-8">`,
- `<title>` i `<h1>` = tytuł raportu z sesji (`_multiseek_report_title`),
- minimalny inline CSS (obramowania tabeli, odstępy listy),
- właściwy `report-body-*` z `export_mode=True`, `start_index=0`,
  `show_footer=True`.

Bez logo, paginatora, paneli, skryptów.

### 4.3 Buildery odpowiedzi (`bpp/views/multiseek_export.py`)

Nowe funkcje:

- `html_export_response(html: str, report_title: str) -> HttpResponse`
  — `text/html; charset=utf-8`, załącznik `eksport-<tytuł>.html`
  (reuse `_export_filename`).
- `docx_export_response(html: str, report_title: str) -> HttpResponse`
  — woła `nowe_raporty.docx_export.html_to_docx(html)` (import lokalny w ciele
  funkcji, jak w `xlsx_export_response`), zwraca
  `application/vnd.openxmlformats-officedocument.wordprocessingml.document`,
  załącznik `.docx`. `DocxConversionError` propaguje (widok mapuje na 500 —
  standardowe, nie tłumimy po cichu).
- `bibtex_export_response(queryset, request, report_title) -> HttpResponse`
  — konkatenacja `rekord.original.to_bibtex` (rozdzielone pustą linią, jak na
  ekranie), `application/x-bibtex; charset=utf-8`, załącznik `.bib`.

Render HTML dokumentu (`render_to_string("multiseek/export-document.html",
ctx, request=request)`) trzymamy w **widoku** (potrzebny `request`/kontekst),
nie w builderze — builder dostaje gotowy string.

### 4.4 Widok `MyMultiseekExport.get`

Rozgałęzienie na starcie wg rodziny formatu:

```
DATA_FORMATS = {"csv", "xlsx"}
DOCUMENT_FORMATS = {"html", "docx", "bib"}
```

- format spoza sumy tych zbiorów → `HttpResponseBadRequest`.
- Wspólnie: limit 5000 (`queryset.count()`), `LoginRequiredMixin`.
- **csv/xlsx**: istniejąca ścieżka bez zmian (zawężenie
  `MULTISEEK_EXPORT_DANE_FIELDS`/`OPIS_FIELDS`, `wariant`).
- **html/docx/bib** (eksport dokumentu):
  - queryset **report_type-aware** z bazowego
    `get_queryset_for_current_mode()` (NIE zawężamy do pól CSV — bazowy
    `get_queryset()` już ma właściwe `.only()`/`select_related` dla EXTRA_TYPES),
  - `report_type = registry.get_report_type(self.get_multiseek_data(),
    request=self.request)`,
  - jeśli `report_type == "bibtex"`:
    - format `bib` → `bibtex_export_response`,
    - format `html`/`docx` w widoku bibtex nie występuje w dropdownie, ale
      gdyby ktoś trafił URL-em ręcznie → degradacja do `.bib` (spójne z D3).
  - w innym razie (lista/tabela):
    - dla typów tabelarycznych (EXTRA_TYPES) doliczamy `sumy`
      (`qset.aggregate(Sum(...), ...)` — reuse logiki z `get_context_data`),
    - `ctx = {"object_list": queryset, "report_type": report_type,
      "sumy": sumy, "report_title": report_title}`,
    - `html = render_to_string("multiseek/export-document.html", ctx,
      request)`,
    - format `html` → `html_export_response`,
    - format `docx` → `docx_export_response`,
    - format `bib` poza widokiem bibtex → `HttpResponseBadRequest`
      („BibTeX dostępny tylko dla widoku BibTeX").

URL bez zmian (`[\w-]+`). Filenames generyczne przez `_export_filename`.

### 4.5 Adaptacyjny dropdown (`templates/multiseek/paginator.html`)

CSV / XLS:dane / XLS:opis — zawsze (bez zmian). Dodatkowo, `report_type`
dostępny w kontekście include'a:

- `report_type == "bibtex"` → jedna pozycja **„BibTeX (.bib)"**
  (`{% url "multiseek-export" "bib" %}`),
- w każdym innym widoku → **„HTML"** (`... "html"`) + **„DOCX (Word)"**
  (`... "docx"`).

Zachowany wzorzec `print_removed` w query-stringu.

## 5. Przepływ danych

```
user klika [Eksport ▸ HTML|DOCX|BibTeX]
  → GET /multiseek/export/<fmt>/[?print-removed=1]
  → MyMultiseekExport.get(fmt)
     ├─ walidacja fmt, limit 5000, login
     ├─ queryset = get_queryset_for_current_mode()   # report_type-aware
     ├─ report_type = registry.get_report_type(...)
     ├─ bibtex? → bibtex_export_response → .bib
     └─ inaczej:
          ├─ sumy (jeśli tabela)
          ├─ html = render_to_string("export-document.html", ctx, request)
          ├─ fmt == html → html_export_response(html) → .html
          └─ fmt == docx → docx_export_response(html)
                            → html_to_docx() [pandoc→docker html2docx] → .docx
```

## 6. Obsługa błędów

- Nieznany format / `bib` poza widokiem bibtex / >5000 rekordów →
  `HttpResponseBadRequest` (spójne z obecnym `csv/xlsx`).
- Anonim → redirect na login (`LoginRequiredMixin`, bez zmian).
- `DocxConversionError` (pandoc i docker padły) → propaguje jako 500; NIE
  tłumimy po cichu (zgodnie z regułą projektu o wyjątkach). Logowanie już
  w `docx_export.py`.

## 7. Testy (TDD)

Plik: `src/bpp/tests/test_views/test_mymultiseek.py` (rozszerzenie) +
ewentualnie nowy `test_multiseek_export_document.py`.

**Buildery odpowiedzi (unit):**
- `html_export_response`: Content-Type `text/html`, Content-Disposition
  `attachment; filename="eksport-*.html"`, treść zawiera markup listy/tabeli.
- `docx_export_response`: monkeypatch `html_to_docx` → sentinel bytes (wzorzec
  z `nowe_raporty/tests/test_docx_export.py`); Content-Type docx, `.docx`
  w Content-Disposition. Dodatkowo **jeden** realny przebieg (pandoc dostępny
  lokalnie) sprawdzający nagłówek ZIP `PK\x03\x04`.
- `bibtex_export_response`: Content-Type `application/x-bibtex`, `.bib`, treść
  zawiera `@` wpisy.

**Routing widoku (integration, `@pytest.mark.django_db`):**
- każdy format (`html`, `docx`, `bib`) → 200 + poprawny Content-Type;
- `report_type` → właściwy render: list vs table (obecność `<ol>` vs `<table>`
  i kolumny wg wariantu tabeli);
- widok bibtex: dropdown/endpoint `bib` → `.bib`; `html`/`docx` degradują do
  `.bib`;
- `bib` w widoku nie-bibtex → 400;
- >5000 rekordów → 400 (mock count);
- anon → redirect;
- nieznany format → 400.

**Regresja partiali:**
- istniejące testy renderu ekranowego (`test_mymultiseek.py`) przechodzą bez
  zmian — potwierdza, że wydzielenie partiali nie zmieniło on-screen output.
- Test „smoke" że `report-body-table.html` renderuje właściwe kolumny dla
  `pkt_wewn` / `pkt_wewn_cytowania` / `table_cytowania` (parametryzowany).

**Uruchomienie lokalnie:** `make tests-without-playwright` + docelowo
`uv run pytest src/bpp/tests/test_views/test_mymultiseek.py`. DOCX-test realny
wymaga pandoca (lokalnie jest); w CI fallback docker lub monkeypatch.

## 8. Pliki (create/modify)

**Modify:**
- `src/bpp/views/mymultiseek.py` — rozgałęzienie `get()`, ścieżka dokumentu,
  liczenie `sumy`, import `render_to_string`.
- `src/bpp/views/multiseek_export.py` — `html_export_response`,
  `docx_export_response`, `bibtex_export_response`.
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
  istniejące testy renderu jako regression gate; refaktor czysto mechaniczny
  (przeniesienie markupu 1:1 + parametry).
- **DOCX na 5000 wierszach** przez pandoc/docker — koszt czasu; limit 5000
  ogranicza, ale realny render dużej tabeli może być wolny. Akceptowalne w v1.
- **`to_bibtex` per rekord** dla BibTeX — potencjalne N+1; ograniczone limitem
  5000. Ewentualna optymalizacja poza zakresem v1.
