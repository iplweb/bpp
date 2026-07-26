# Wachlarz wyjść dla „Wyszukiwania zapytaniem" — plan wdrożenia

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strona `/zapytanie/` (DjangoQL) dostaje pełny wachlarz wyjść multiseeka
(postać wyniku + eksport CSV/XLSX/HTML/DOCX/BibTeX + tabela krzyżowa), a model
`Autor` dostaje własny rejestr tabeli krzyżowej i eksport kartoteki z metrykami
dorobku.

**Architecture:** Warstwa wyjścia (eksport, pivot) jest funkcją *querysetu*, nie
multiseeka. Wyciągamy trzy rzeczy do wspólnego użytku (`wykonaj_zapytanie`,
`document_export_response`, pakiet `bpp/pivot/`), a strona zapytania staje się
drugim konsumentem tej samej warstwy. Rejestr pivota autorskiego wprowadza
pojęcie **bazy agregacji** (K/P/U), bo ten sam wymiar ma różną ścieżkę ORM
w zależności od wybranej metryki.

**Tech Stack:** Django 5, DjangoQL (`apply_search`), django-multiseek, openpyxl,
pytest + model_bakery, Foundation CSS.

**Spec:** `docs/superpowers/specs/2026-07-26-zapytanie-wachlarz-wyjsc-design.md`

## Global Constraints

- **Max line length: 88 znaków** (ruff). Formatowanie: `ruff format .`, potem
  `ruff check .`. Nigdy `ruff check --fix`.
- **Wszystkie komendy Pythona przez `uv run`.** Nigdy gołe `python`/`pytest`.
- **Testy: pytest bez klas**, funkcje `test_*`, `@pytest.mark.django_db`,
  obiekty przez `model_bakery.baker.make`. Nigdy `unittest.TestCase`.
- **Komentarze i teksty UI po polsku.** Komentarz wyjaśnia DLACZEGO, nie CO.
- **Komentarze w szablonach Django: każda linia własne `{# ... #}`.** Komentarz
  wieloliniowy wycieka do HTML-a.
- **Zero `except Exception: pass`.** Każdy `except` loguje, re-raise'uje albo
  zwraca sensowny błąd.
- **Nie modyfikować istniejących migracji.** Ten plan nie tworzy żadnych
  migracji — nie ma zmian w modelach.
- **Newsfragment po każdej fazie** w `src/bpp/newsfragments/<slug>.feature.rst`
  (kanoniczny katalog; `changes/newsfragments/` NIE działa).
- **Istniejące testy pivota (`test_multiseek_pivot.py` 17 testów,
  `test_multiseek_pivot_view.py` 8 testów) nie wolno zmieniać** — są dowodem
  neutralności refaktoru E3.
- Wszystkie nowe endpointy pod `WprowadzanieDanychOrSuperuserMixin`
  (`raise_exception = True` → 403).

## Konwencje testowe tego repo — PRZECZYTAJ PRZED PISANIEM TESTÓW

Te trzy rzeczy wywalą Ci testy, jeśli ich nie zastosujesz. Snippety w zadaniach
niżej ich **nie powtarzają** — stosuj je wszędzie, gdzie pasują.

**1. `Rekord` to zdenormalizowany cache — trzeba go zmaterializować.**
Utworzenie `Wydawnictwo_Ciagle`/`Wydawnictwo_Zwarte` NIE pojawia się od razu
w `Rekord.objects`. Każdy test, który tworzy publikację i potem odpytuje
`Rekord` (bezpośrednio albo przez `wykonaj_zapytanie("rekord", …)`, widok,
eksport czy pivot), **musi** przyjąć fixture `denorms` i po utworzeniu danych
wywołać `denorms.flush()`:

```python
@pytest.mark.django_db
def test_czegos(denorms, wydawnictwo_ciagle):
    denorms.flush()
    ...
```

To samo dotyczy `wydawnictwo_ciagle.dodaj_autora(...)` — po dodaniu autorstwa
`denorms.flush()`, inaczej `bpp_autorzy_mat` nie zobaczy powiązania. Wzorzec do
podejrzenia: `src/bpp/tests/test_multiseek_pivot.py` (fixture `rekordy_pivot`).

**2. Fixture `tytul` (pojedynczy) NIE ISTNIEJE.** Jest `tytuly` — ładuje słownik
tytułów i nic nie zwraca. Gdzie plan pisze „fixture `tytul`", zrób obiekt sam:

```python
from bpp.models import Tytul

tytul = baker.make(Tytul, nazwa="doktor", skrot="dr")
```

**3. Fixtures, które istnieją i których masz używać:** `wydawnictwo_ciagle`,
`wydawnictwo_zwarte`, `autor_jan_nowak`, `autor_jan_kowalski`, `jednostka`,
`dyscyplina1`, `denorms`, `tytuly`, `charaktery_formalne`, `typy_kbn`,
`jezyki`, `statusy_korekt`, `typy_odpowiedzialnosci`, `admin_user`, `rf`,
`client`, `django_user_model`. Definicje: `src/fixtures/conftest_*.py`
i `src/conftest.py`. Nie wymyślaj nowych, jeśli któryś z tych wystarcza.

**4. Uruchamianie testów — TYLKO przez wrapper, nie gołym `uv run pytest`:**

```bash
bash .superpowers/sdd/2026-07-26-zapytanie-wachlarz-wyjsc/pytest.sh src/bpp/tests/test_zapytanie.py -v
```

Wrapper przyjmuje te same argumenty co pytest. **Gołe `uv run pytest` na tym
hoście PADNIE** na `ContainerStartError`: OrbStack nie ma uprawnień macOS do
wolumenu `/Volumes/SSD`, a plugin testcontainers montuje stamtąd
`baseline-sql/baseline.sql` do kontenera PG (mount → „Operation not
permitted" → kontener umiera w initdb). Wrapper omija to, kierując testy na
ręcznie wystawione kontenery `bpp-wyj-pg` (port 55432) i `bpp-wyj-redis`
(56379), do których baseline wgrano przez `docker cp`. Szczegóły i procedura
odtworzenia kontenerów: komentarz w nagłówku `pytest.sh`.

Suita ma `--reuse-db` i `--timeout 90` (test dłuższy niż 90 s = fail).
Referencyjny czas: `test_zapytanie.py` ≈ 40 s.

**NIE uruchamiaj `make clean-testcontainers`** ani `docker rm` na kontenerach,
których nie stworzyłeś — na tym hoście biegną kontenery innych worktree
i skasowałbyś cudzą pracę. Kontenery `bpp-wyj-*` są wspólne dla wszystkich
zadań tego planu; nie kasuj ich po swoim zadaniu.

## Struktura plików

| plik | odpowiedzialność |
|---|---|
| `src/bpp/views/zapytanie.py` (modyfikacja) | `wykonaj_zapytanie()`, `ZapytanieView` + `postac`, kontekst pivota |
| `src/bpp/views/zapytanie_export.py` (nowy) | `ZapytanieExportView` — routing formatów, capy, tytuł |
| `src/bpp/views/multiseek_export.py` (modyfikacja) | + `document_export_response()`, + eksport autorów |
| `src/bpp/views/mymultiseek.py` (modyfikacja) | `_export_document` deleguje do funkcji |
| `src/bpp/pivot/__init__.py` (nowy) | re-eksport publicznego API pakietu |
| `src/bpp/pivot/core.py` (nowy) | generyk: dataclasses, macierz, etykiety, bramki, strategie |
| `src/bpp/pivot/rekord.py` (nowy) | rejestr wymiarów/metryk `Rekord` (przeniesione) |
| `src/bpp/pivot/autor.py` (nowy) | rejestr wymiarów/metryk `Autor` + bazy K/P/U |
| `src/bpp/multiseek_registry/pivot.py` (modyfikacja) | cienki re-eksport z `bpp.pivot` |
| `src/bpp/templates/bpp/zapytanie.html` (modyfikacja) | pasek postaci + pasek eksportu + include partiali |
| `src/django_bpp/templates/multiseek/report-body-list.html` (modyfikacja) | flagi `hide_chrome`, `pokaz_edycje` |
| `src/django_bpp/templates/multiseek/report-body-table.html` (modyfikacja) | flaga `hide_chrome` |
| `src/bpp/urls.py` (modyfikacja) | route `zapytanie/eksport/<format>/` |
| `src/bpp/tests/test_zapytanie_postac.py` (nowy) | render postaci, neutralność flag szablonowych |
| `src/bpp/tests/test_zapytanie_export.py` (nowy) | formaty, capy, uprawnienia, sanityzacja tytułu |
| `src/bpp/tests/test_pivot_autor.py` (nowy) | engine autorski: bazy K/P/U, adnotacje, dedup |
| `src/bpp/tests/test_zapytanie_pivot.py` (nowy) | pivot na stronie zapytania (rekord + autor) |

---

## FAZA 1 — wspólny silnik wyjścia + eksporty rekordów

### Task 1: `wykonaj_zapytanie()` — jedno źródło prawdy dla querysetu

**Files:**
- Modify: `src/bpp/views/zapytanie.py` (dodaj funkcję; `render_results` ma jej użyć)
- Test: `src/bpp/tests/test_zapytanie.py` (dopisz do istniejącego pliku)

**Interfaces:**
- Produces: `wykonaj_zapytanie(model_key: str, query: str) -> WynikZapytania`,
  gdzie `WynikZapytania` to `NamedTuple` z polami
  `queryset` (`QuerySet | None`), `error` (`str | None`),
  `error_location` (`dict | None`). Przy błędzie `queryset is None`.
  Funkcja NIE stronicuje i NIE liczy `count()`.

- [ ] **Step 1: Write the failing test**

W `src/bpp/tests/test_zapytanie.py` dopisz:

```python
@pytest.mark.django_db
def test_wykonaj_zapytanie_zwraca_queryset(wydawnictwo_ciagle):
    from bpp.views.zapytanie import wykonaj_zapytanie

    wynik = wykonaj_zapytanie("rekord", f"rok = {wydawnictwo_ciagle.rok}")

    assert wynik.error is None
    assert wynik.queryset.count() == 1


@pytest.mark.django_db
def test_wykonaj_zapytanie_zwraca_blad_z_lokalizacja():
    from bpp.views.zapytanie import wykonaj_zapytanie

    wynik = wykonaj_zapytanie("rekord", "rok ===")

    assert wynik.queryset is None
    assert wynik.error
    assert wynik.error_location["line"] >= 1


@pytest.mark.django_db
def test_wykonaj_zapytanie_dedupuje_po_relacji_do_wielu(
    denorms, wydawnictwo_ciagle, autor_jan_nowak, jednostka, jednostka_podrzedna
):
    """Filtr po autorach mnoży wiersze rekordu — distinct() musi je zwinąć.

    KLUCZOWE: ten sam autor musi być przypisany do rekordu DWA razy (dwie
    jednostki), inaczej w bpp_autorzy_mat jest jeden wiersz, JOIN zwraca
    jeden wynik i test przechodzi także BEZ distinct() — czyli nie chroni
    przed niczym. Wzorzec: fixture rekord_z_autorem_w_dwoch_jednostkach
    w src/bpp/tests/test_views/test_browse/test_browse_distinct.py.
    """
    from bpp.views.zapytanie import wykonaj_zapytanie

    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)
    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka_podrzedna)
    denorms.flush()

    wynik = wykonaj_zapytanie("rekord", 'autorzy.autor.nazwisko = "Nowak"')

    assert wynik.queryset.count() == 1
```

**Weryfikacja siły tego testu (wymagana):** usuń tymczasowo `.distinct()`
z `wykonaj_zapytanie`, uruchom ten test — MUSI paść (`assert 2 == 1`). Test
regresyjny, który nie pada po usunięciu chronionego zachowania, jest
tautologią. Potem przywróć `.distinct()`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_zapytanie.py -k wykonaj_zapytanie -v`
Expected: FAIL — `ImportError: cannot import name 'wykonaj_zapytanie'`

- [ ] **Step 3: Write minimal implementation**

W `src/bpp/views/zapytanie.py`, po `_resolve_model_or_404` (albo nad
`ZapytanieView`, byle po `MODELS`):

```python
class WynikZapytania(NamedTuple):
    """Queryset albo błąd — jedno źródło prawdy dla strony i eksportu."""

    queryset: object | None
    error: str | None
    error_location: dict | None


def wykonaj_zapytanie(model_key, query):
    """Zamienia zapytanie DjangoQL na queryset wskazanego modelu.

    Wydzielone z ZapytanieView.render_results, żeby eksport liczył DOKŁADNIE
    ten sam zbiór co strona — łącznie z .distinct(), bez którego filtr po
    relacji "do wielu" (np. autorzy.autor.nazwisko) zwielokrotniłby rekord
    raz na każdy pasujący wiersz powiązany.
    """
    model = MODELS[model_key]
    try:
        queryset = apply_search(
            model.objects.all(), query, schema=BppZapytanieSchema
        ).distinct()
    except (DjangoQLError, FieldError, ValidationError, ValueError) as exc:
        line, column, mark = _error_location(exc, query)
        location = (
            {"line": line, "column": column, "mark": mark} if line and column else None
        )
        return WynikZapytania(None, _format_error_text(exc), location)
    return WynikZapytania(queryset, None, None)
```

Dodaj `from typing import NamedTuple` do importów.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_zapytanie.py -k wykonaj_zapytanie -v`
Expected: PASS (3 testy)

- [ ] **Step 5: Przepnij `render_results` na nową funkcję**

W `ZapytanieView.render_results` zastąp blok `try/except` wywołaniem:

```python
    def render_results(self, form):
        model_key = form.cleaned_data["model"]
        query = form.cleaned_data["query"].strip()
        wynik = wykonaj_zapytanie(model_key, query)
        results_page = None
        count = None

        if wynik.queryset is not None:
            count = wynik.queryset.count()
            paginator = Paginator(wynik.queryset, self.paginate_by)
            page_number = self.request.GET.get("page") or 1
            results_page = paginator.get_page(page_number)

        if results_page is not None and model_key == MODEL_REKORD:
            self._attach_admin_urls(results_page)

        context = self.get_context_data(
            form=form,
            results=results_page,
            count=count,
            error=wynik.error,
            error_location=wynik.error_location,
            model_key=model_key,
            query=query,
        )
        return self.render_to_response(context)
```

- [ ] **Step 6: Cała dotychczasowa suita zapytania musi przejść bez zmian**

Run: `uv run pytest src/bpp/tests/test_zapytanie.py -q`
Expected: PASS — zero zmian w istniejących testach (dowód neutralności E1)

- [ ] **Step 7: Commit**

```bash
uv run ruff format src/bpp/views/zapytanie.py src/bpp/tests/test_zapytanie.py
uv run ruff check src/bpp/views/zapytanie.py src/bpp/tests/test_zapytanie.py
git add src/bpp/views/zapytanie.py src/bpp/tests/test_zapytanie.py
git commit -m "refactor(zapytanie): wykonaj_zapytanie() jako jedno źródło prawdy"
```

---

### Task 2: `document_export_response()` — ekstrakcja renderu dokumentu

**Files:**
- Modify: `src/bpp/views/multiseek_export.py` (dodaj funkcję na końcu)
- Modify: `src/bpp/views/mymultiseek.py:349-399` (`_export_document` → delegacja)
- Test: `src/bpp/tests/test_multiseek_export.py` (dopisz; jeśli plik nie
  istnieje — utwórz)

**Interfaces:**
- Consumes: nic z Task 1.
- Produces: `document_export_response(queryset, request, report_type,
  report_title, export_format) -> HttpResponse`. `export_format` ∈
  `{"html", "docx"}`. Funkcja sama dobiera partial i projekcję `.only()` wg
  `report_type`, sama liczy `sumy` dla postaci tabelarycznych. Dla
  `report_type == "bibtex"` **nie** jest wołana (BibTeX ma własną ścieżkę).

- [ ] **Step 1: Write the failing test**

```python
import pytest
from model_bakery import baker

from bpp.models import Rekord


@pytest.mark.django_db
def test_document_export_response_html_zawiera_opis(rf, wydawnictwo_ciagle):
    from bpp.views.multiseek_export import document_export_response

    request = rf.get("/")
    response = document_export_response(
        Rekord.objects.all(), request, "list", "Tytuł", "html"
    )

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/html")
    assert b"multiseek-list-report" in response.content


@pytest.mark.django_db
def test_document_export_response_tabela_ma_sumy(rf, wydawnictwo_ciagle):
    from bpp.views.multiseek_export import document_export_response

    wydawnictwo_ciagle.punkty_kbn = 40
    wydawnictwo_ciagle.save()
    request = rf.get("/")
    response = document_export_response(
        Rekord.objects.all(), request, "table", "Tytuł", "html"
    )

    assert b"multiseek-table-report" in response.content


@pytest.mark.django_db
def test_document_export_response_docx(rf, wydawnictwo_ciagle):
    from bpp.views.multiseek_export import document_export_response

    request = rf.get("/")
    response = document_export_response(
        Rekord.objects.all(), request, "list", "Tytuł", "docx"
    )

    assert "wordprocessingml" in response["Content-Type"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_multiseek_export.py -k document_export -v`
Expected: FAIL — `ImportError: cannot import name 'document_export_response'`

- [ ] **Step 3: Write minimal implementation**

Do `multiseek_export.py` przenieś ciało `MyMultiseekExport._export_document`
(bez pobierania `report_type` z registry — dostaje je parametrem). Stałe
`MULTISEEK_RENDER_LIST_FIELDS`, `MULTISEEK_RENDER_TABLE_FIELDS` i zbiór
`TABLE_REPORT_TYPES` przenieś z `mymultiseek.py` do `multiseek_export.py`
i re-eksportuj z `mymultiseek.py` (`from bpp.views.multiseek_export import
TABLE_REPORT_TYPES  # noqa: F401`), żeby nie zepsuć importów w testach.

```python
def document_export_response(
    queryset, request, report_type, report_title, export_format
):
    """Render postaci wyniku (lista/tabela) do HTML-a albo DOCX-a.

    Wydzielone z MyMultiseekExport._export_document: metoda nie używała self
    do niczego poza odczytem report_type, a strona „Wyszukiwanie zapytaniem"
    potrzebuje tej samej ścieżki renderu. Jeden zestaw partiali, jedna
    sanityzacja, jedna konwersja do DOCX.
    """
    from django.db.models import Sum
    from django.template.loader import render_to_string

    if report_type in TABLE_REPORT_TYPES:
        queryset = queryset.select_related("charakter_formalny", "typ_kbn").only(
            *MULTISEEK_RENDER_TABLE_FIELDS
        )
        sumy = queryset.aggregate(
            Sum("impact_factor"),
            Sum("liczba_cytowan"),
            Sum("punkty_kbn"),
            Sum("punktacja_wewnetrzna"),
        )
        partial = "multiseek/report-body-table.html"
    else:
        queryset = queryset.only(*MULTISEEK_RENDER_LIST_FIELDS)
        sumy = None
        partial = "multiseek/report-body-list.html"

    body_html = render_to_string(
        partial,
        {
            "object_list": queryset,
            "report_type": report_type,
            "sumy": sumy,
            "export_mode": True,
            "start_index": 0,
        },
        request=request,
    )
    document_html = render_to_string(
        "multiseek/export-document.html",
        {
            "body_html": sanitize_export_html(body_html),
            "report_title": report_title,
        },
        request=request,
    )
    if export_format == "docx":
        return docx_export_response(document_html, report_title)
    return html_export_response(document_html, report_title)
```

**UWAGA:** `TABLE_REPORT_TYPES` w `mymultiseek.py` to `frozenset(EXTRA_TYPES)`,
gdzie `EXTRA_TYPES` zawiera `table`, `pkt_wewn`, `pkt_wewn_bez` i warianty
`_cytowania`. Przenieś oba (`EXTRA_TYPES` i `TABLE_REPORT_TYPES`) razem ze
stałymi `PKT_WEWN`, `PKT_WEWN_BEZ`, `TABLE`, żeby nie rozdzielać definicji.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_multiseek_export.py -k document_export -v`
Expected: PASS (3 testy)

- [ ] **Step 5: Przepnij `MyMultiseekExport._export_document` na delegację**

```python
    def _export_document(self, request, export_format, queryset, report_title):
        registry = get_registry(self.registry)
        report_type = registry.get_report_type(
            self.get_multiseek_data(), request=request
        )
        if report_type == "bibtex":
            # W widoku BibTeX html/docx degradują do .bib (D3).
            return bibtex_export_response(queryset, report_title)
        if export_format == "bib":
            return HttpResponseBadRequest("BibTeX dostępny tylko w widoku BibTeX.")
        return document_export_response(
            queryset, request, report_type, report_title, export_format
        )
```

- [ ] **Step 6: Cała suita multiseeka musi przejść bez zmian w testach**

Run: `uv run pytest src/bpp/tests/ -k multiseek -q`
Expected: PASS (dowód neutralności E2)

- [ ] **Step 7: Commit**

```bash
uv run ruff format src/bpp/views/multiseek_export.py src/bpp/views/mymultiseek.py
uv run ruff check src/bpp/views/multiseek_export.py src/bpp/views/mymultiseek.py
git add src/bpp/views/ src/bpp/tests/test_multiseek_export.py
git commit -m "refactor(multiseek): document_export_response() jako funkcja"
```

---

### Task 3: parametr `postac` i render partiali na `/zapytanie/`

**Files:**
- Modify: `src/bpp/views/zapytanie.py` (`POSTACIE`, `ZapytanieForm`, kontekst)
- Modify: `src/bpp/templates/bpp/zapytanie.html` (pasek postaci + include)
- Modify: `src/django_bpp/templates/multiseek/report-body-list.html`
- Modify: `src/django_bpp/templates/multiseek/report-body-table.html`
- Test: `src/bpp/tests/test_zapytanie_postac.py` (nowy)

**Interfaces:**
- Consumes: `wykonaj_zapytanie()` z Task 1.
- Produces: stałe w `bpp/views/zapytanie.py`:
  `POSTAC_REKORDY = "rekordy"`, `POSTACIE_REKORD` (tuple par
  `(wartość, etykieta)`: `rekordy`, `lista`, `tabela`, `pkt_wewn`,
  `pkt_wewn_bez`, `bibtex`, `pivot`), `POSTACIE_AUTOR`
  (`rekordy`, `pivot`), oraz `parse_postac(GET, model_key) -> str`
  (nieznana/niedozwolona wartość → `POSTAC_REKORDY`).

- [ ] **Step 1: Write the failing test**

`src/bpp/tests/test_zapytanie_postac.py`:

```python
import pytest
from django.urls import reverse


@pytest.fixture
def zalogowany_redaktor(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.mark.django_db
def test_postac_domyslna_to_tabela_redakcyjna(zalogowany_redaktor, wydawnictwo_ciagle):
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "rekord", "query": f"rok = {wydawnictwo_ciagle.rok}"},
    )
    assert res.status_code == 200
    assert b"rekord-id-cell" in res.content


@pytest.mark.django_db
def test_postac_lista_renderuje_partial_multiseeka(
    zalogowany_redaktor, wydawnictwo_ciagle
):
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "list",
        },
    )
    assert b"multiseek-list-report" in res.content


@pytest.mark.django_db
def test_postac_lista_nie_pokazuje_widgetu_usuwania(
    zalogowany_redaktor, wydawnictwo_ciagle
):
    """Widget ❌ jest sesyjny i multiseekowy — na /zapytanie/ nie działałby."""
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "list",
        },
    )
    assert b"data-remove-result" not in res.content


@pytest.mark.django_db
def test_postac_tabela_ma_sumy(zalogowany_redaktor, wydawnictwo_ciagle):
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "table",
        },
    )
    assert b"multiseek-table-report" in res.content


@pytest.mark.django_db
def test_postac_niedozwolona_dla_autora_degraduje(zalogowany_redaktor, autor_jan_nowak):
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "autor", "query": 'nazwisko = "Nowak"', "postac": "bibtex"},
    )
    assert res.status_code == 200
    assert b"multiseek-list-report" not in res.content


@pytest.mark.django_db
def test_multiseek_nadal_pokazuje_widget_usuwania(client, wydawnictwo_ciagle):
    """Dowód neutralności flagi hide_chrome: multiseek jej nie przekazuje."""
    from django.template.loader import render_to_string

    from bpp.models import Rekord

    html = render_to_string(
        "multiseek/report-body-list.html",
        {"object_list": Rekord.objects.all(), "export_mode": False},
    )
    assert "data-remove-result" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_zapytanie_postac.py -v`
Expected: FAIL — `postac=list` nie renderuje partiala (brak
`multiseek-list-report`)

- [ ] **Step 3: Zmodyfikuj partiale (flagi `hide_chrome`, `pokaz_edycje`)**

W `report-body-list.html` zmień warunek chrome i dodaj link edycji:

```django
        {% if not export_mode and not print_removed and not hide_chrome %}
            <span class="multiseek-remove-from-results">
                <a data-remove-result="{{ element.js_safe_pk }}" style="font-size: 8pt;">
                    ❌
                </a>
            </span>
        {% endif %}
        {# pokaz_edycje: flaga strony „Wyszukiwanie zapytaniem"; multiseek jej #}
        {# nie przekazuje, więc tam blok jest wyłączony (brak zmiennej = falsy). #}
        {% if pokaz_edycje and element.admin_url %}
            <span class="zapytanie-edytuj">
                <a href="{{ element.admin_url }}" target="_blank"
                   title="Edytuj w panelu administracyjnym">✎</a>
            </span>
        {% endif %}
```

W `report-body-table.html` — ten sam warunek `hide_chrome` przy widgecie ❌
(znajdź `data-remove-result` i dołóż `and not hide_chrome`).

- [ ] **Step 4: Dodaj `postac` do widoku**

W `src/bpp/views/zapytanie.py`:

```python
POSTAC_REKORDY = "rekordy"
POSTAC_PIVOT = "pivot"

# UWAGA: `pivot` NIE jest tu wymieniony celowo. Postać widoczna w <select>
# ma działać — pivot rekordowy dokłada zadanie 6, autorski zadanie 9 i to
# one dopisują go do tych krotek. Opcja, która renderuje placeholder, jest
# gorsza niż jej brak.
POSTACIE_REKORD = (
    (POSTAC_REKORDY, "rekordy (ID + akcje)"),
    ("list", "lista"),
    ("table", "tabela"),
    ("pkt_wewn", "punktacja z wewnętrzną"),
    ("pkt_wewn_bez", "punktacja sumaryczna"),
    ("bibtex", "BibTeX"),
)
POSTACIE_AUTOR = ((POSTAC_REKORDY, "autorzy (ID + akcje)"),)


def postacie_dla_modelu(model_key):
    return POSTACIE_AUTOR if model_key == MODEL_AUTOR else POSTACIE_REKORD


def parse_postac(GET, model_key):
    """Postać wyniku z GET-a, z cichą degradacją do domyślnej.

    Cicha degradacja (nie 400), bo postać przychodzi z linku/zakładki, a
    zmiana modelu w formularzu może unieważnić wcześniejszy wybór — user nie
    ma wtedy nic złego na sumieniu.
    """
    dozwolone = {key for key, _ in postacie_dla_modelu(model_key)}
    postac = GET.get("postac") or POSTAC_REKORDY
    return postac if postac in dozwolone else POSTAC_REKORDY
```

W `render_results` dołóż do kontekstu `postac`, `postacie` i — dla postaci
innych niż `rekordy`/`pivot` — projekcję querysetu oraz `sumy`:

```python
        postac = parse_postac(self.request.GET, model_key)
        ...
        if results_page is not None and model_key == MODEL_REKORD:
            self._attach_admin_urls(results_page)

        sumy = None
        if postac in TABLE_REPORT_TYPES and wynik.queryset is not None:
            sumy = wynik.queryset.aggregate(
                Sum("impact_factor"),
                Sum("liczba_cytowan"),
                Sum("punkty_kbn"),
                Sum("punktacja_wewnetrzna"),
            )

        context = self.get_context_data(
            ...,
            postac=postac,
            postacie=postacie_dla_modelu(model_key),
            sumy=sumy,
        )
```

Import: `from bpp.views.multiseek_export import TABLE_REPORT_TYPES`.

- [ ] **Step 5: Podłącz include w `bpp/zapytanie.html`**

W bloku `{% if results %}` (linia ~452) rozgałęź render. Zachowaj istniejącą
tabelę pod `postac == "rekordy"`:

```django
                {% include "bpp/_zapytanie_pager.html" %}
                {% if postac == "rekordy" %}
                    {# dotychczasowa tabela redakcyjna — bez zmian #}
                    <table class="hover stack">
                    ...
                    </table>
                {% elif postac == "table" or postac == "pkt_wewn" or postac == "pkt_wewn_bez" %}
                    {% include "multiseek/report-body-table.html" with object_list=results report_type=postac sumy=sumy export_mode=False hide_chrome=True pokaz_edycje=request.user.is_staff start_index=results.start_index|add:"-1" %}
                {% else %}
                    {% include "multiseek/report-body-list.html" with object_list=results report_type=postac export_mode=False hide_chrome=True pokaz_edycje=request.user.is_staff start_index=results.start_index|add:"-1" %}
                {% endif %}
                {% include "bpp/_zapytanie_pager.html" %}
```

Nad formularzem (obok `.zapytanie-toolbar`, linia ~375) dodaj pasek wyboru
postaci jako `<select name="postac">` w formularzu GET — postać musi jechać
razem z zapytaniem, żeby „Szukaj" ją zachowywał:

```django
            <label for="id_postac" style="margin-top: 0.6rem;">
                Postać wyniku
                <select name="postac" id="id_postac">
                    {% for value, label in postacie %}
                        <option value="{{ value }}"
                                {% if postac == value %}selected{% endif %}>{{ label }}</option>
                    {% endfor %}
                </select>
            </label>
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest src/bpp/tests/test_zapytanie_postac.py src/bpp/tests/test_zapytanie.py -q`
Expected: PASS (nowe + wszystkie stare)

- [ ] **Step 7: Sprawdź, że multiseek nadal działa**

Run: `uv run pytest src/bpp/tests/ -k multiseek -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
uv run ruff format src/bpp/views/zapytanie.py src/bpp/tests/test_zapytanie_postac.py
uv run ruff check src/bpp/views/zapytanie.py src/bpp/tests/test_zapytanie_postac.py
git add src/bpp/views/zapytanie.py src/bpp/templates/bpp/zapytanie.html \
        src/django_bpp/templates/multiseek/report-body-list.html \
        src/django_bpp/templates/multiseek/report-body-table.html \
        src/bpp/tests/test_zapytanie_postac.py
git commit -m "feat(zapytanie): postać wyniku (lista/tabela/punktacja) z partiali multiseeka"
```

---

### Task 4: `ZapytanieExportView` — eksport rekordów w 5 formatach

**Files:**
- Create: `src/bpp/views/zapytanie_export.py`
- Modify: `src/bpp/urls.py` (route obok istniejących `zapytanie/...`)
- Test: `src/bpp/tests/test_zapytanie_export.py` (nowy)

**Interfaces:**
- Consumes: `wykonaj_zapytanie()` (Task 1), `document_export_response()`
  (Task 2), `parse_postac()` (Task 3).
- Produces: URL o nazwie `bpp:zapytanie_eksport` z parametrem ścieżki
  `export_format`; stałe `ZAPYTANIE_EXPORT_MAX_DANE = 25000`,
  `ZAPYTANIE_EXPORT_MAX_DOKUMENT = 5000`,
  `ZAPYTANIE_DEFAULT_REPORT_TITLE = "Wynik zapytania"`.

- [ ] **Step 1: Write the failing test**

`src/bpp/tests/test_zapytanie_export.py`:

```python
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from bpp.const import GR_WPROWADZANIE_DANYCH


def url(export_format, **params):
    return (
        reverse("bpp:zapytanie_eksport", kwargs={"export_format": export_format})
        + "?"
        + "&".join(f"{k}={v}" for k, v in params.items())
    )


@pytest.fixture
def redaktor(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.mark.django_db
def test_eksport_csv_ma_naglowek_i_wiersz(redaktor, wydawnictwo_ciagle):
    res = redaktor.get(url("csv", model="rekord", query=f"rok+%3D+{wydawnictwo_ciagle.rok}"))

    assert res.status_code == 200
    assert res["Content-Type"].startswith("text/csv")
    assert b"tytul_oryginalny" in res.content


@pytest.mark.django_db
def test_eksport_xlsx(redaktor, wydawnictwo_ciagle):
    res = redaktor.get(url("xlsx", model="rekord", query=f"rok+%3D+{wydawnictwo_ciagle.rok}"))

    assert "spreadsheetml" in res["Content-Type"]


@pytest.mark.django_db
def test_eksport_html_z_postaci_lista(redaktor, wydawnictwo_ciagle):
    res = redaktor.get(
        url("html", model="rekord", query=f"rok+%3D+{wydawnictwo_ciagle.rok}", postac="list")
    )

    assert res["Content-Type"].startswith("text/html")
    assert b"multiseek-list-report" in res.content


@pytest.mark.django_db
def test_eksport_bib_tylko_przy_postaci_bibtex(redaktor, wydawnictwo_ciagle):
    zle = redaktor.get(
        url("bib", model="rekord", query=f"rok+%3D+{wydawnictwo_ciagle.rok}", postac="list")
    )
    assert zle.status_code == 400

    dobrze = redaktor.get(
        url("bib", model="rekord", query=f"rok+%3D+{wydawnictwo_ciagle.rok}", postac="bibtex")
    )
    assert dobrze.status_code == 200
    assert "bibtex" in dobrze["Content-Type"]


@pytest.mark.django_db
def test_eksport_nieznany_format_400(redaktor):
    res = redaktor.get(url("pdf", model="rekord", query="rok+%3D+2024"))
    assert res.status_code == 400


@pytest.mark.django_db
def test_eksport_bledne_zapytanie_400(redaktor):
    res = redaktor.get(url("csv", model="rekord", query="rok+%3D%3D%3D"))
    assert res.status_code == 400


@pytest.mark.django_db
def test_eksport_anonim_403(client, wydawnictwo_ciagle):
    res = client.get(url("csv", model="rekord", query="rok+%3D+2024"))
    assert res.status_code in (302, 403)


@pytest.mark.django_db
def test_eksport_staff_poza_grupa_403(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="staff", password="x", is_staff=True
    )
    client.force_login(user)
    res = client.get(url("csv", model="rekord", query="rok+%3D+2024"))
    assert res.status_code == 403


@pytest.mark.django_db
def test_eksport_staff_w_grupie_ma_dostep(client, django_user_model, wydawnictwo_ciagle):
    user = django_user_model.objects.create_user(
        username="redaktor2", password="x", is_staff=True
    )
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(group)
    client.force_login(user)
    res = client.get(url("csv", model="rekord", query=f"rok+%3D+{wydawnictwo_ciagle.rok}"))
    assert res.status_code == 200


@pytest.mark.django_db
def test_eksport_sanityzuje_tytul_w_naglowku(redaktor, wydawnictwo_ciagle):
    """Tytuł jest w pełni user-controlled i trafia do Content-Disposition."""
    res = redaktor.get(
        reverse("bpp:zapytanie_eksport", kwargs={"export_format": "csv"}),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "tytul": 'zły"tytuł\n../etc/passwd',
        },
    )

    disposition = res["Content-Disposition"]
    assert "\n" not in disposition
    assert "../" not in disposition


@pytest.mark.django_db
def test_eksport_dokumentu_powyzej_capu_400(redaktor, wydawnictwo_ciagle, monkeypatch):
    from bpp.views import zapytanie_export

    monkeypatch.setattr(zapytanie_export, "ZAPYTANIE_EXPORT_MAX_DOKUMENT", 0)
    res = redaktor.get(
        url("html", model="rekord", query=f"rok+%3D+{wydawnictwo_ciagle.rok}", postac="list")
    )
    assert res.status_code == 400
    # Komunikat czyta limit ze stałej modułu (monkeypatch = 0), więc nie może
    # być zaszytego „5000" w tekście.
    assert b"maksymalnie 0 rekord" in res.content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_zapytanie_export.py -v`
Expected: FAIL — `NoReverseMatch: 'zapytanie_eksport' is not a valid view`

- [ ] **Step 3: Write minimal implementation**

`src/bpp/views/zapytanie_export.py`:

```python
"""Eksport wyników „Wyszukiwania zapytaniem" (DjangoQL).

Widok trzyma routing formatów i limity; zamianę querysetu na plik robi
bpp.views.multiseek_export — ta sama warstwa, której używa multiseek.
"""

from django.http import HttpResponseBadRequest
from django.views.generic import View

from bpp.views.multiseek_export import (
    MULTISEEK_EXPORT_DANE_FIELDS,
    MULTISEEK_EXPORT_OPIS_FIELDS,
    bibtex_export_response,
    csv_export_response,
    document_export_response,
    plain_multiseek_report_title,
    xlsx_export_response,
)
from bpp.views.zapytanie import (
    MODEL_REKORD,
    WprowadzanieDanychOrSuperuserMixin,
    parse_postac,
    wykonaj_zapytanie,
)

ZAPYTANIE_EXPORT_MAX_DANE = 25000
ZAPYTANIE_EXPORT_MAX_DOKUMENT = 5000
ZAPYTANIE_DEFAULT_REPORT_TITLE = "Wynik zapytania"

DATA_FORMATS = {"csv", "xlsx"}
DOCUMENT_FORMATS = {"html", "docx", "bib"}


class ZapytanieExportView(WprowadzanieDanychOrSuperuserMixin, View):
    http_method_names = ["get"]

    def get(self, request, export_format, *args, **kwargs):
        if export_format not in DATA_FORMATS | DOCUMENT_FORMATS:
            return HttpResponseBadRequest("Nieznany format eksportu.")

        model_key = request.GET.get("model") or MODEL_REKORD
        query = (request.GET.get("query") or "").strip()
        if not query:
            return HttpResponseBadRequest("Brak zapytania do wyeksportowania.")
        if model_key != MODEL_REKORD:
            return HttpResponseBadRequest(
                "Eksport autorów zostanie dodany w kolejnym kroku."
            )

        wynik = wykonaj_zapytanie(model_key, query)
        if wynik.queryset is None:
            return HttpResponseBadRequest(f"Błędne zapytanie: {wynik.error}")

        postac = parse_postac(request.GET, model_key)
        report_title = plain_multiseek_report_title(
            request.GET.get("tytul") or ZAPYTANIE_DEFAULT_REPORT_TITLE
        )
        queryset = wynik.queryset
        count = queryset.count()

        if export_format in DATA_FORMATS:
            if count > ZAPYTANIE_EXPORT_MAX_DANE:
                return self._za_duzo(count, ZAPYTANIE_EXPORT_MAX_DANE)
            return self._eksport_danych(request, export_format, queryset, report_title)

        if count > ZAPYTANIE_EXPORT_MAX_DOKUMENT:
            return self._za_duzo(count, ZAPYTANIE_EXPORT_MAX_DOKUMENT)

        if export_format == "bib":
            if postac != "bibtex":
                return HttpResponseBadRequest(
                    "BibTeX dostępny tylko przy postaci wyniku „BibTeX"."
                )
            return bibtex_export_response(queryset, report_title)
        if postac == "bibtex":
            return bibtex_export_response(queryset, report_title)

        # postac=rekordy to tabela redakcyjna z ID i linkami do admina — jako
        # dokument do wydruku nie ma sensu, więc degradujemy do listy.
        report_type = "list" if postac == "rekordy" else postac
        return document_export_response(
            queryset, request, report_type, report_title, export_format
        )

    @staticmethod
    def _za_duzo(count, limit):
        return HttpResponseBadRequest(
            f"Eksport dostępny dla maksymalnie {limit} rekordów "
            f"(zapytanie zwróciło {count}). Zawęź zapytanie."
        )

    @staticmethod
    def _eksport_danych(request, export_format, queryset, report_title):
        wariant = request.GET.get("wariant", "dane")
        if export_format == "csv" or wariant not in {"dane", "opis"}:
            wariant = "dane"

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

W `src/bpp/urls.py`, w bloku importów z `bpp.views.zapytanie` (linia ~95) dodaj
osobny import i route obok pozostałych `zapytanie/...` (po `zapytanie/explain/`):

```python
    path(
        "zapytanie/eksport/<str:export_format>/",
        ZapytanieExportView.as_view(),
        name="zapytanie_eksport",
    ),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/bpp/tests/test_zapytanie_export.py -v`
Expected: PASS (11 testów)

- [ ] **Step 5: Commit**

```bash
uv run ruff format src/bpp/views/zapytanie_export.py src/bpp/urls.py src/bpp/tests/test_zapytanie_export.py
uv run ruff check src/bpp/views/zapytanie_export.py src/bpp/urls.py src/bpp/tests/test_zapytanie_export.py
git add src/bpp/views/zapytanie_export.py src/bpp/urls.py src/bpp/tests/test_zapytanie_export.py
git commit -m "feat(zapytanie): eksport CSV/XLSX/HTML/DOCX/BibTeX z zapytania DjangoQL"
```

---

### Task 5: pasek eksportu w UI + newsfragment fazy 1

**Files:**
- Modify: `src/bpp/templates/bpp/zapytanie.html`
- Create: `src/bpp/newsfragments/zapytanie-eksporty.feature.rst`

**Interfaces:**
- Consumes: URL `bpp:zapytanie_eksport` (Task 4), zmienne kontekstu `postac`,
  `query`, `model_key`, `count` (Task 3).

- [ ] **Step 1: Dodaj pasek eksportu pod nagłówkiem wyników**

W `bpp/zapytanie.html`, zaraz po `<h2>Wyniki (...)</h2>`:

```django
            {% if results %}
                <p class="zapytanie-eksport-toolbar">
                    <strong>Eksport:</strong>
                    {% for fmt, label in eksport_formaty %}
                        <a class="button tiny secondary"
                           href="{% url 'bpp:zapytanie_eksport' export_format=fmt %}?model={{ model_key|urlencode }}&amp;query={{ query|urlencode }}&amp;postac={{ postac|urlencode }}">{{ label }}</a>
                    {% endfor %}
                </p>
            {% endif %}
```

W `ZapytanieView.render_results` dołóż do kontekstu listę formatów zależną od
modelu i postaci — BibTeX tylko przy `postac=bibtex`, dokumenty tylko dla
rekordów:

```python
def eksport_formaty(model_key, postac):
    """Formaty eksportu sensowne dla danego modelu i postaci wyniku."""
    if model_key == MODEL_AUTOR:
        return (("csv", "CSV"), ("xlsx", "XLSX"))
    formaty = [("csv", "CSV"), ("xlsx", "XLSX")]
    if postac == POSTAC_PIVOT:
        return tuple(formaty)
    formaty += [("html", "HTML"), ("docx", "DOCX")]
    if postac == "bibtex":
        formaty.append(("bib", "BibTeX (.bib)"))
    return tuple(formaty)
```

- [ ] **Step 2: Test paska**

Dopisz do `src/bpp/tests/test_zapytanie_postac.py`:

```python
@pytest.mark.django_db
def test_pasek_eksportu_ma_link_do_csv(zalogowany_redaktor, wydawnictwo_ciagle):
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "rekord", "query": f"rok = {wydawnictwo_ciagle.rok}"},
    )
    assert b"/zapytanie/eksport/csv/" in res.content


@pytest.mark.django_db
def test_pasek_eksportu_bez_bibtexa_przy_liscie(
    zalogowany_redaktor, wydawnictwo_ciagle
):
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "list",
        },
    )
    assert b"/zapytanie/eksport/bib/" not in res.content
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest src/bpp/tests/test_zapytanie_postac.py -q`
Expected: PASS

- [ ] **Step 4: Newsfragment**

`src/bpp/newsfragments/zapytanie-eksporty.feature.rst`:

```rst
Wyszukiwanie zapytaniem (DjangoQL) pozwala teraz wybrać postać wyniku
(rekordy, lista, tabela, punktacja, BibTeX) i wyeksportować wyniki do CSV,
XLSX, HTML, DOCX oraz BibTeX-a — tak jak multiwyszukiwarka.
```

- [ ] **Step 5: Commit**

```bash
git add src/bpp/templates/bpp/zapytanie.html src/bpp/views/zapytanie.py \
        src/bpp/newsfragments/zapytanie-eksporty.feature.rst \
        src/bpp/tests/test_zapytanie_postac.py
git commit -m "feat(zapytanie): pasek eksportu w UI + newsfragment"
```

---

## FAZA 2 — tabela krzyżowa rekordów na `/zapytanie/`

### Task 6: `postac=pivot` dla rekordów + eksport macierzy

**Files:**
- Modify: `src/bpp/views/zapytanie.py` (kontekst pivota)
- Modify: `src/bpp/views/zapytanie_export.py` (rozgałęzienie pivota)
- Modify: `src/bpp/templates/bpp/zapytanie.html` (include partiala pivota)
- Test: `src/bpp/tests/test_zapytanie_pivot.py` (nowy)

**Interfaces:**
- Consumes: `bpp.multiseek_registry.pivot.{parse_pivot_params, zbuduj_pivot,
  DIMENSIONS, METRICS, PivotTooLargeError}` — **na tym etapie jeszcze ze
  starej lokalizacji** (przeprowadzka to Task 7).
- Produces: klucze kontekstu identyczne z multiseekiem, żeby
  `report-body-pivot.html` działał bez zmian: `pivot`, `pivot_error`,
  `pivot_dimensions`, `pivot_metrics`, `pivot_row_dim`, `pivot_col_dim`,
  `pivot_metric`.

- [ ] **Step 1: Write the failing test**

```python
import pytest
from django.urls import reverse


@pytest.fixture
def redaktor(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.mark.django_db
def test_pivot_rekordow_renderuje_macierz(redaktor, wydawnictwo_ciagle):
    res = redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "pivot",
            "pivot_row": "rok",
            "pivot_val": "liczba",
        },
    )
    assert res.status_code == 200
    assert res.context["pivot"].grand_total == 1
    assert str(wydawnictwo_ciagle.rok).encode() in res.content


@pytest.mark.django_db
def test_pivot_rekordow_z_kolumna(redaktor, wydawnictwo_ciagle):
    res = redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "pivot",
            "pivot_row": "rok",
            "pivot_col": "typ_kbn",
            "pivot_val": "liczba",
        },
    )
    assert res.context["pivot"].col_dim.key == "typ_kbn"


@pytest.mark.django_db
def test_pivot_eksport_csv_zwraca_macierz(redaktor, wydawnictwo_ciagle):
    res = redaktor.get(
        reverse("bpp:zapytanie_eksport", kwargs={"export_format": "csv"}),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "pivot",
            "pivot_row": "rok",
            "pivot_val": "liczba",
        },
    )
    assert res.status_code == 200
    assert b"RAZEM" in res.content


@pytest.mark.django_db
def test_pivot_eksport_html_400(redaktor, wydawnictwo_ciagle):
    res = redaktor.get(
        reverse("bpp:zapytanie_eksport", kwargs={"export_format": "html"}),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "pivot",
        },
    )
    assert res.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_zapytanie_pivot.py -v`
Expected: FAIL — `res.context["pivot"]` nie istnieje (KeyError)

- [ ] **Step 2b: Dopisz `pivot` do listy postaci rekordowych**

W `src/bpp/views/zapytanie.py` dodaj `(POSTAC_PIVOT, "tabela krzyżowa")` na
końcu `POSTACIE_REKORD`. Zadanie 3 celowo go stamtąd wyrzuciło, bo bez
implementacji z tego zadania opcja renderowała placeholder listy. Teraz
działa, więc wraca do UI.

- [ ] **Step 3: Kontekst pivota w widoku**

W `ZapytanieView.render_results`, po ustaleniu `postac`, przed budowaniem
kontekstu:

```python
        pivot_ctx = {}
        if postac == POSTAC_PIVOT and wynik.queryset is not None:
            pivot_ctx = self._pivot_context(model_key, wynik.queryset)
```

i metoda:

```python
    def _pivot_context(self, model_key, queryset):
        """Kontekst tabeli krzyżowej — klucze zgodne z multiseekiem, żeby
        partial report-body-pivot.html renderował się bez zmian."""
        from bpp.multiseek_registry import pivot as pivot_mod

        row_dim, col_dim, metric = pivot_mod.parse_pivot_params(self.request.GET)
        ctx = {
            "pivot_dimensions": pivot_mod.DIMENSIONS,
            "pivot_metrics": pivot_mod.METRICS,
            "pivot_row_dim": row_dim,
            "pivot_col_dim": col_dim,
            "pivot_metric": metric,
        }
        try:
            ctx["pivot"] = pivot_mod.zbuduj_pivot(queryset, row_dim, col_dim, metric)
        except pivot_mod.PivotTooLargeError as exc:
            ctx["pivot"] = None
            ctx["pivot_error"] = exc
        return ctx
```

`pivot_ctx` przekaż do `get_context_data(**pivot_ctx, ...)`.

- [ ] **Step 4: Include partiala w szablonie**

W rozgałęzieniu z Task 3 dodaj gałąź `pivot` **przed** pagerem (pivot nie jest
stronicowany):

```django
                {% if postac == "pivot" %}
                    {% include "multiseek/report-body-pivot.html" %}
                {% else %}
                    {% include "bpp/_zapytanie_pager.html" %}
                    ... (pozostałe postacie) ...
                    {% include "bpp/_zapytanie_pager.html" %}
                {% endif %}
```

**Trzy KONIECZNE zmiany w `report-body-pivot.html`** (bez nich pivot na
`/zapytanie/` jest zepsuty; wszystkie z domyślnymi wartościami, więc multiseek
zachowuje się identycznie jak dziś):

**P1. Formularz selektorów musi przenosić stan strony zapytania.** Dziś jest
`<form method="get" action=".">` z samymi selektami pivota — na `/zapytanie/`
submit zgubiłby `model` i `query` (multiseek trzyma filtr w sesji, strona
zapytania w URL-u). Zmień na:

```django
    <form method="get" action="{{ pivot_form_action|default:'.' }}"
          class="multiseek-pivot-controls">
        {# Ukryte pola przenoszą stan konsumenta (na /zapytanie/: model, #}
        {# query, postac). Multiseek nie przekazuje pivot_form_hidden — #}
        {# jego filtr żyje w sesji, więc pętla jest pusta. #}
        {% for name, value in pivot_form_hidden %}
            <input type="hidden" name="{{ name }}" value="{{ value }}">
        {% endfor %}
```

**P2. Linki eksportu są relatywne i zakładają głębokość URL-a multiseeka.**
`../export/xlsx/` na `/multiseek/results/` trafia w `/multiseek/export/`, ale na
`/zapytanie/` rozwiąże się do `/export/xlsx/` → 404. Zmień oba linki na:

```django
    {% if request.user.is_authenticated %}
    {% with base=pivot_export_base|default:"../export/" %}
    <div class="multiseek-pivot-export hide-for-print">
        Eksport tabeli:
        <a href="{{ base }}xlsx/?{{ request.GET.urlencode }}">XLSX</a>
        <a href="{{ base }}csv/?{{ request.GET.urlencode }}">CSV</a>
    </div>
    {% endwith %}
    {% endif %}
```

**P3. Kontekst z widoku zapytania musi te trzy zmienne podać:**

```python
        ctx["pivot_form_action"] = reverse("bpp:zapytanie")
        ctx["pivot_form_hidden"] = [
            ("model", model_key),
            ("query", self.request.GET.get("query", "")),
            ("postac", POSTAC_PIVOT),
        ]
        ctx["pivot_export_base"] = "/zapytanie/eksport/"
```

`pivot_export_base` zbuduj z `reverse`, nie z literału — użyj
`reverse("bpp:zapytanie_eksport", kwargs={"export_format": "csv"})` i utnij
końcowe `csv/`, albo (czytelniej) dodaj w `urls.py` pomocniczy prefiks. Literał
w kodzie zerwie się przy zmianie routingu.

- [ ] **Step 5: Rozgałęzienie eksportu**

W `ZapytanieExportView.get`, po sprawdzeniu formatu i wykonaniu zapytania,
**przed** capami:

```python
        if postac == POSTAC_PIVOT:
            # Pivot eksportuje MACIERZ — jej rozmiar nie zależy od liczby
            # rekordów źródłowych, więc capy rekordowe go nie dotyczą
            # (dokładnie jak w MyMultiseekExport.get).
            return self._eksport_pivota(request, export_format, queryset, report_title)
```

```python
    @staticmethod
    def _eksport_pivota(request, export_format, queryset, report_title):
        from bpp.multiseek_registry import pivot as pivot_mod
        from bpp.views.multiseek_export import (
            pivot_csv_export_response,
            pivot_xlsx_export_response,
        )

        if export_format not in {"csv", "xlsx"}:
            return HttpResponseBadRequest(
                "Eksport tabeli krzyżowej dostępny jako XLSX lub CSV."
            )
        row_dim, col_dim, metric = pivot_mod.parse_pivot_params(request.GET)
        try:
            pivot_result = pivot_mod.zbuduj_pivot(queryset, row_dim, col_dim, metric)
        except pivot_mod.PivotTooLargeError:
            return HttpResponseBadRequest(
                "Tabela krzyżowa jest zbyt duża do wyeksportowania — "
                "zawęź zapytanie lub wybierz mniej liczny wymiar."
            )
        if export_format == "csv":
            return pivot_csv_export_response(pivot_result, request, report_title)
        return pivot_xlsx_export_response(pivot_result, request, report_title)
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest src/bpp/tests/test_zapytanie_pivot.py src/bpp/tests/test_zapytanie_postac.py src/bpp/tests/test_zapytanie_export.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
uv run ruff format src/bpp/views/ src/bpp/tests/test_zapytanie_pivot.py
uv run ruff check src/bpp/views/ src/bpp/tests/test_zapytanie_pivot.py
git add src/bpp/views/ src/bpp/templates/bpp/zapytanie.html \
        src/django_bpp/templates/multiseek/report-body-pivot.html \
        src/bpp/tests/test_zapytanie_pivot.py
git commit -m "feat(zapytanie): tabela krzyżowa rekordów z eksportem CSV/XLSX"
```

---

## FAZA 3 — pakiet `bpp/pivot/` + rejestr autorski (baza K)

### Task 7: przeprowadzka pivota do `bpp/pivot/` (neutralna)

**Files:**
- Create: `src/bpp/pivot/__init__.py`, `src/bpp/pivot/core.py`,
  `src/bpp/pivot/rekord.py`
- Modify: `src/bpp/multiseek_registry/pivot.py` → cienki re-eksport
- Modify: `src/bpp/views/zapytanie.py`, `src/bpp/views/zapytanie_export.py`
  (importy na nową lokalizację)

**Interfaces:**
- Produces: `bpp.pivot.core.{PivotDimension, PivotMetric, PivotResult,
  PivotTooLargeError, BRAK, PIVOT_MAX_CELLS, PIVOT_MAX_PAIRS, zbuduj_pivot,
  buduj_macierz, etykiety}`; `bpp.pivot.rekord.{DIMENSIONS, METRICS,
  DEFAULT_ROW, DEFAULT_METRIC, parse_pivot_params}`.
- **Kluczowa zmiana sygnatury:** `zbuduj_pivot(base_qs, row_dim, col_dim,
  metric, *, model=None)` — `model` to model bazowy dla strategii dedupu
  (domyślnie `bpp.models.cache.Rekord`, żeby istniejące wywołania działały bez
  zmian).

- [ ] **Step 1: Uruchom testy pivota PRZED zmianą — zapisz wynik**

Run: `uv run pytest src/bpp/tests/test_multiseek_pivot.py src/bpp/tests/test_multiseek_pivot_view.py -q`
Expected: PASS, 25 passed. Zapisz liczbę — po przeprowadzce musi być identyczna.

- [ ] **Step 2: Przenieś kod**

`src/bpp/pivot/core.py` — z `multiseek_registry/pivot.py` przenieś: `BRAK`,
`PivotDimension`, `PivotMetric`, `PivotResult`, `PIVOT_MAX_CELLS`,
`PIVOT_MAX_PAIRS`, `PivotTooLargeError`, `_annotate`, `zbuduj_pivot`,
`_dedup_strategy`, `_pairs_strategy`, `_build_matrix`, `_labels`,
`_format_pk_bucket`, `_label_mapping`.

W `zbuduj_pivot` i `_dedup_strategy` sparametryzuj model:

```python
def zbuduj_pivot(base_qs, row_dim, col_dim, metric, *, model=None):
    if model is None:
        from bpp.models.cache import Rekord

        model = Rekord
    ...
    triples = (
        _pairs_strategy(base_qs, row_dim, col_dim, metric)
        if has_autorzy
        else _dedup_strategy(base_qs, row_dim, col_dim, metric, model)
    )


def _dedup_strategy(base_qs, row_dim, col_dim, metric, model):
    """(...) świeży queryset modelu bazowego bez wcześniejszych JOIN-ów."""
    deduped = model.objects.filter(pk__in=base_qs.values("pk")).order_by()
    ...
```

`src/bpp/pivot/rekord.py` — `DIMENSIONS`, `METRICS`, `DEFAULT_ROW`,
`DEFAULT_METRIC`, `parse_pivot_params` (importuje `PivotDimension`/`PivotMetric`
z `.core`).

`src/bpp/pivot/__init__.py`:

```python
"""Tabele krzyżowe (pivot) — generyczny silnik + rejestry per model."""

from .core import (  # noqa: F401
    BRAK,
    PIVOT_MAX_CELLS,
    PIVOT_MAX_PAIRS,
    PivotDimension,
    PivotMetric,
    PivotResult,
    PivotTooLargeError,
    zbuduj_pivot,
)
```

`src/bpp/multiseek_registry/pivot.py` — cały plik zastąp:

```python
"""Zgodnościowy re-eksport: silnik pivota żyje w bpp.pivot.

Rejestr wymiarów Rekordu przestał być multiseek-specyficzny w momencie, gdy
tabelę krzyżową dostała też strona „Wyszukiwanie zapytaniem". Ten moduł
zostaje, żeby nie ruszać call-site'ów w szablonach, widokach i testach.
"""

from bpp.pivot.core import (  # noqa: F401
    BRAK,
    PIVOT_MAX_CELLS,
    PIVOT_MAX_PAIRS,
    PivotDimension,
    PivotMetric,
    PivotResult,
    PivotTooLargeError,
    zbuduj_pivot,
)
from bpp.pivot.rekord import (  # noqa: F401
    DEFAULT_METRIC,
    DEFAULT_ROW,
    DIMENSIONS,
    METRICS,
    parse_pivot_params,
)
```

- [ ] **Step 3: Testy pivota MUSZĄ przejść bez zmian w plikach testowych**

Run: `uv run pytest src/bpp/tests/test_multiseek_pivot.py src/bpp/tests/test_multiseek_pivot_view.py -q`
Expected: PASS, 25 passed — dokładnie tyle samo co w Step 1.

Jeśli którykolwiek test wymaga zmiany → przeprowadzka NIE jest neutralna,
popraw kod produkcyjny, nie test.

**Uwaga o prywatnych nazwach:** testy mogą importować `_dedup_strategy`,
`_pairs_strategy` albo `_labels`. Jeśli tak — re-eksportuj je również w shimie.
Sprawdź: `grep -n "pivot import\|pivot\._" src/bpp/tests/test_multiseek_pivot*.py`

- [ ] **Step 4: Przepnij nowe call-site'y na `bpp.pivot`**

W `zapytanie.py` i `zapytanie_export.py` zamień
`from bpp.multiseek_registry import pivot as pivot_mod` na
`from bpp.pivot import rekord as pivot_rekord` + `from bpp.pivot import core as
pivot_core` (albo import konkretnych nazw). Multiseek zostaje na shimie —
migrację jego importów zostawiamy na kiedyś, nie jest częścią tej pracy.

- [ ] **Step 5: Run full zapytanie + multiseek suite**

Run: `uv run pytest src/bpp/tests/ -k "pivot or zapytanie or multiseek" -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
uv run ruff format src/bpp/pivot/ src/bpp/multiseek_registry/pivot.py src/bpp/views/
uv run ruff check src/bpp/pivot/ src/bpp/multiseek_registry/pivot.py src/bpp/views/
git add src/bpp/pivot/ src/bpp/multiseek_registry/pivot.py src/bpp/views/
git commit -m "refactor(pivot): silnik do bpp/pivot/, multiseek_registry re-eksportuje"
```

---

### Task 8: rejestr autorski, baza K (kadrowa)

**Files:**
- Create: `src/bpp/pivot/autor.py`
- Modify: `src/bpp/pivot/core.py` (obsługa `annotation` i `expr` per baza)
- Test: `src/bpp/tests/test_pivot_autor.py` (nowy)

**Interfaces:**
- Consumes: `bpp.pivot.core` (Task 7).
- Produces:
  - `bpp.pivot.core.PivotDimension` zyskuje pola
    `annotation: Callable | None = None` i akceptuje `expr` typu
    `str | dict[str, str]`; metoda `expr_dla(baza: str) -> str | None`
    (None = wymiar niedostępny w tej bazie).
  - `bpp.pivot.core.PivotMetric` zyskuje pola `baza: str = "K"`,
    `distinct_field: str | None = None` (gdy ustawione → `Count(field,
    distinct=True)`).
  - `bpp.pivot.autor.{DIMENSIONS, METRICS, DEFAULT_ROW, DEFAULT_METRIC,
    parse_pivot_params_autor(GET), zbuduj_pivot_autora(base_qs, row_dim,
    col_dim, metric)}`.
  - Stałe baz: `BAZA_KADROWA = "K"`, `BAZA_PRACE = "P"`, `BAZA_UDZIALY = "U"`.

- [ ] **Step 1: Write the failing test**

`src/bpp/tests/test_pivot_autor.py`:

```python
import pytest
from model_bakery import baker

from bpp.models import Autor


@pytest.mark.django_db
def test_baza_kadrowa_liczy_autorow(jednostka):
    from bpp.pivot.autor import METRICS, DIMENSIONS, zbuduj_pivot_autora

    baker.make(Autor, aktualna_jednostka=jednostka, _quantity=3)
    baker.make(Autor, aktualna_jednostka=None)

    wynik = zbuduj_pivot_autora(
        Autor.objects.all(), DIMENSIONS["jednostka"], None, METRICS["liczba_autorow"]
    )

    assert wynik.grand_total == 4
    etykiety = dict(wynik.rows)
    assert 3 in [wynik.row_totals[k] for k in wynik.row_totals]
    assert "— brak —" in etykiety.values()


@pytest.mark.django_db
def test_wymiar_ma_orcid_grupuje_na_tak_nie():
    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    baker.make(Autor, orcid="0000-0001-0000-0001")
    baker.make(Autor, orcid=None, _quantity=2)

    wynik = zbuduj_pivot_autora(
        Autor.objects.all(), DIMENSIONS["ma_orcid"], None, METRICS["liczba_autorow"]
    )

    etykiety = {label: wynik.row_totals[key] for key, label in wynik.rows}
    assert etykiety == {"TAK": 1, "NIE": 2}


@pytest.mark.django_db
def test_krzyzowo_jednostka_x_tytul(jednostka, tytul):
    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    baker.make(Autor, aktualna_jednostka=jednostka, tytul=tytul, _quantity=2)

    wynik = zbuduj_pivot_autora(
        Autor.objects.all(),
        DIMENSIONS["jednostka"],
        DIMENSIONS["tytul"],
        METRICS["liczba_autorow"],
    )

    assert wynik.grand_total == 2
    assert len(wynik.cols) == 1


@pytest.mark.django_db
def test_rok_urodzenia_jako_wymiar():
    import datetime

    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    baker.make(Autor, urodzony=datetime.date(1970, 5, 1))
    baker.make(Autor, urodzony=datetime.date(1980, 5, 1))

    wynik = zbuduj_pivot_autora(
        Autor.objects.all(),
        DIMENSIONS["rok_urodzenia"],
        None,
        METRICS["liczba_autorow"],
    )

    assert {label for _, label in wynik.rows} >= {"1970", "1980"}


@pytest.mark.django_db
def test_dedup_nie_zwielokrotnia_przy_filtrze_do_wielu(jednostka):
    """Filtr po relacji do-wielu mnoży wiersze autora — dedup musi je zwinąć."""
    from bpp.models import Autor_Jednostka
    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    autor = baker.make(Autor, aktualna_jednostka=jednostka)
    baker.make(Autor_Jednostka, autor=autor, jednostka=jednostka, _quantity=2)

    qs = Autor.objects.filter(autor_jednostka__jednostka=jednostka)
    wynik = zbuduj_pivot_autora(
        qs, DIMENSIONS["jednostka"], None, METRICS["liczba_autorow"]
    )

    assert wynik.grand_total == 1


@pytest.mark.django_db
def test_parse_params_odrzuca_wymiar_niedostepny_w_bazie():
    from bpp.pivot.autor import parse_pivot_params_autor

    row, col, metric = parse_pivot_params_autor(
        {"pivot_row": "rok", "pivot_val": "liczba_autorow"}
    )

    # „rok" jest wymiarem publikacyjnym — w bazie kadrowej niedostępny.
    assert row.key != "rok"


@pytest.mark.django_db
def test_bramka_rozmiaru_macierzy(monkeypatch, jednostka):
    from bpp.pivot import core
    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    baker.make(Autor, aktualna_jednostka=jednostka, _quantity=3)
    monkeypatch.setattr(core, "PIVOT_MAX_CELLS", 0)

    with pytest.raises(core.PivotTooLargeError):
        zbuduj_pivot_autora(
            Autor.objects.all(),
            DIMENSIONS["autor"],
            None,
            METRICS["liczba_autorow"],
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_pivot_autor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bpp.pivot.autor'`

- [ ] **Step 3: Rozszerz `core.PivotDimension` / `PivotMetric`**

```python
@dataclass(frozen=True)
class PivotDimension:
    key: str
    label: str
    expr: str | dict  # str = jedna ścieżka; dict = ścieżka per baza agregacji
    allow_column: bool = True
    autorzy: bool = False
    label_kind: str = "raw"  # raw | fk | choices_charakter_ogolny | pk_bucket | bool
    fk_model: str | None = None
    # Wyrażenie ORM dokładane przez annotate() PRZED grupowaniem. Konieczne
    # dla wymiarów, które nie są kolumną (np. „ma ORCID": grupowanie po
    # surowym polu dałoby tysiące grup, po jednej na wartość).
    annotation: object | None = None

    def expr_dla(self, baza=None):
        """Ścieżka ORM w danej bazie agregacji; None = niedostępny."""
        if isinstance(self.expr, dict):
            return self.expr.get(baza)
        return self.expr

    def alias(self, baza=None):
        """Nazwa pola do values()/GROUP BY — alias adnotacji albo ścieżka."""
        return self.key if self.annotation is not None else self.expr_dla(baza)
```

`PivotMetric`:

```python
@dataclass(frozen=True)
class PivotMetric:
    key: str
    label: str
    field: str | None  # None → Count("id"); inaczej Sum(field)
    baza: str = "K"  # która baza agregacji (rejestr autorski); rekordowy: "K"
    distinct_field: str | None = None  # ustawione → Count(field, distinct=True)
```

Etykiety `bool`:

```python
    if dim.label_kind == "bool":
        return {
            k: ("TAK" if k is True else "NIE" if k is False else BRAK) for k in keys
        }
```

- [ ] **Step 4: Napisz `bpp/pivot/autor.py`**

```python
"""Rejestr tabeli krzyżowej dla modelu Autor.

Trzy bazy agregacji, bo metryka decyduje o ścieżce JOIN-u:

* K (kadrowa) — sam bpp_autor, metryka „liczba autorów";
* P (prace)   — przez `autorzy` (mat. view) do rekordu, metryka „liczba prac";
* U (udziały) — przez `cache_punktacja_autora_query` (ma FK do Rekordu, więc
  widzi rok), metryki Σ slotów i Σ pkdaut.

Świadomie NIE ma Σ IF / Σ PK / Σ cytowań: to wartości rekordowe, które
sumowane per autor zwielokrotniają się między współautorami. Kto ich chce,
używa pivota REKORDOWEGO z wymiarem „jednostka" — tam strategia par liczy je
poprawnie.
"""

from django.db.models import BooleanField, Case, Count, Sum, Value, When

from .core import (
    PIVOT_MAX_CELLS,
    PivotDimension,
    PivotMetric,
    PivotTooLargeError,
    buduj_macierz,
)

BAZA_KADROWA = "K"
BAZA_PRACE = "P"
BAZA_UDZIALY = "U"
WSZYSTKIE_BAZY = (BAZA_KADROWA, BAZA_PRACE, BAZA_UDZIALY)

DEFAULT_ROW = "jednostka"
DEFAULT_METRIC = "liczba_autorow"


def _ma_wartosc(pole):
    """Adnotacja TAK/NIE dla pola tekstowego/FK, które bywa puste albo NULL."""
    return Case(
        When(**{f"{pole}__isnull": True}, then=Value(False)),
        When(**{pole: ""}, then=Value(False)),
        default=Value(True),
        output_field=BooleanField(),
    )


def _ma_fk(pole):
    return Case(
        When(**{f"{pole}__isnull": True}, then=Value(False)),
        default=Value(True),
        output_field=BooleanField(),
    )


def _autorski(expr):
    """Wymiar autorski — ta sama ścieżka we wszystkich bazach."""
    return {baza: expr for baza in WSZYSTKIE_BAZY}


DIMENSIONS: dict[str, PivotDimension] = {
    "jednostka": PivotDimension(
        "jednostka",
        "Aktualna jednostka",
        _autorski("aktualna_jednostka_id"),
        allow_column=False,
        label_kind="fk",
        fk_model="bpp.Jednostka",
    ),
    "tytul": PivotDimension(
        "tytul",
        "Tytuł naukowy",
        _autorski("tytul_id"),
        label_kind="fk",
        fk_model="bpp.Tytul",
    ),
    "stopien_sluzbowy": PivotDimension(
        "stopien_sluzbowy",
        "Stopień służbowy",
        _autorski("stopien_sluzbowy_id"),
        label_kind="fk",
        fk_model="bpp.StopienSluzbowy",
    ),
    "funkcja": PivotDimension(
        "funkcja",
        "Aktualna funkcja",
        _autorski("aktualna_funkcja_id"),
        label_kind="fk",
        fk_model="bpp.Funkcja_Autora",
    ),
    "plec": PivotDimension(
        "plec",
        "Płeć",
        _autorski("plec_id"),
        label_kind="fk",
        fk_model="bpp.Plec",
    ),
    "ma_orcid": PivotDimension(
        "ma_orcid",
        "Ma ORCID",
        _autorski("ma_orcid"),
        label_kind="bool",
        annotation=_ma_wartosc("orcid"),
    ),
    "orcid_w_pbn": PivotDimension(
        "orcid_w_pbn",
        "ORCID w PBN",
        _autorski("orcid_w_pbn"),
        label_kind="bool",
    ),
    "ma_pbn_uid": PivotDimension(
        "ma_pbn_uid",
        "Ma PBN UID",
        _autorski("ma_pbn_uid"),
        label_kind="bool",
        annotation=_ma_fk("pbn_uid"),
    ),
    "ma_email": PivotDimension(
        "ma_email",
        "Ma e-mail",
        _autorski("ma_email"),
        label_kind="bool",
        annotation=_ma_wartosc("email"),
    ),
    "ma_id_kadrowy": PivotDimension(
        "ma_id_kadrowy",
        "Ma ID kadrowy",
        _autorski("ma_id_kadrowy"),
        label_kind="bool",
        annotation=_ma_fk("system_kadrowy_id"),
    ),
    "rok_urodzenia": PivotDimension(
        "rok_urodzenia",
        "Rok urodzenia",
        _autorski("urodzony__year"),
    ),
    "autor": PivotDimension(
        "autor",
        "Autor",
        _autorski("pk"),
        allow_column=False,
        label_kind="fk",
        fk_model="bpp.Autor",
    ),
}

METRICS: dict[str, PivotMetric] = {
    "liczba_autorow": PivotMetric(
        "liczba_autorow", "Liczba autorów", None, baza=BAZA_KADROWA,
        distinct_field="pk",
    ),
}


def parse_pivot_params_autor(GET):
    """Wiersz/kolumna/metryka dla pivota autorskiego.

    Metryka wybiera bazę; wymiar niedostępny w tej bazie jest cicho
    zastępowany domyślnym (analogicznie do allow_column w pivocie
    rekordowym) — parametry przychodzą z linków i zakładek, więc twardy
    błąd byłby wrogi.
    """
    metric = METRICS.get(GET.get("pivot_val") or "", METRICS[DEFAULT_METRIC])
    row = DIMENSIONS.get(GET.get("pivot_row") or "", DIMENSIONS[DEFAULT_ROW])
    if row.expr_dla(metric.baza) is None:
        row = DIMENSIONS[DEFAULT_ROW]
    col = DIMENSIONS.get(GET.get("pivot_col") or "")
    if col is not None and (
        not col.allow_column
        or col.key == row.key
        or col.expr_dla(metric.baza) is None
    ):
        col = None
    return row, col, metric


def zbuduj_pivot_autora(base_qs, row_dim, col_dim, metric):
    """Macierz pivota autorskiego — czysty SQL (COUNT DISTINCT / SUM).

    Dedup: agregujemy na ŚWIEŻYM querysecie Autora zawężonym do PK-ów
    wejściowego zbioru, bo filtry DjangoQL mogą łączyć relacje do-wielu
    i zwielokrotniać wiersze autora (ta sama zasada, co _dedup_strategy
    w pivocie rekordowym).
    """
    from bpp.models import Autor

    qs = Autor.objects.filter(pk__in=base_qs.values("pk")).order_by()
    baza = metric.baza

    adnotacje = {}
    for dim in (row_dim, col_dim):
        if dim is not None and dim.annotation is not None:
            adnotacje[dim.key] = dim.annotation
    if adnotacje:
        qs = qs.annotate(**adnotacje)

    grupy = [row_dim.alias(baza)]
    if col_dim is not None:
        grupy.append(col_dim.alias(baza))

    n_cells = qs.values(*grupy).distinct().count()
    if n_cells > PIVOT_MAX_CELLS:
        raise PivotTooLargeError(n_cells, PIVOT_MAX_CELLS, "cells")

    if metric.distinct_field:
        agregat = Count(metric.distinct_field, distinct=True)
    else:
        agregat = Sum(metric.field)

    triples = []
    for wiersz in qs.values(*grupy).annotate(val=agregat):
        rk = wiersz[row_dim.alias(baza)]
        ck = wiersz[col_dim.alias(baza)] if col_dim is not None else None
        val = wiersz["val"] or 0
        if baza != BAZA_KADROWA and not val:
            # Autor bez dorobku wchodzi przez LEFT JOIN z NULL-em — nie
            # zapychamy nim macierzy.
            continue
        triples.append((rk, ck, val))

    return buduj_macierz(triples, row_dim, col_dim, metric, False)
```

**W `core.py`** dorób publiczny alias `buduj_macierz = _build_matrix`
(nowy kod nie powinien wołać prywatnych nazw) i przekaż `baza` do `_labels`
tam, gdzie potrzebne (`_labels` używa `dim.key`, więc zmiany nie wymaga).

- [ ] **Step 5: Run tests**

Run: `uv run pytest src/bpp/tests/test_pivot_autor.py -v`
Expected: PASS (7 testów)

- [ ] **Step 6: Testy pivota rekordowego nadal zielone**

Run: `uv run pytest src/bpp/tests/test_multiseek_pivot.py src/bpp/tests/test_multiseek_pivot_view.py -q`
Expected: PASS, 25 passed

- [ ] **Step 7: Commit**

```bash
uv run ruff format src/bpp/pivot/ src/bpp/tests/test_pivot_autor.py
uv run ruff check src/bpp/pivot/ src/bpp/tests/test_pivot_autor.py
git add src/bpp/pivot/ src/bpp/tests/test_pivot_autor.py
git commit -m "feat(pivot): rejestr autorski, baza kadrowa (liczba autorów)"
```

---

### Task 9: pivot autorski w UI + presety

**Files:**
- Modify: `src/bpp/views/zapytanie.py` (`_pivot_context` rozgałęzia po modelu)
- Modify: `src/bpp/views/zapytanie_export.py` (eksport pivota autorskiego)
- Modify: `src/bpp/templates/bpp/zapytanie.html` (presety w pomocy)
- Test: `src/bpp/tests/test_zapytanie_pivot.py` (dopisz)

**Interfaces:**
- Consumes: `bpp.pivot.autor` (Task 8).
- Produces: klucz kontekstu `pivot_presety` — lista słowników
  `{"opis": str, "query": str}` z gotowymi query-stringami.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.django_db
def test_pivot_autorow_jednostka_x_tytul(redaktor, jednostka, tytul):
    from model_bakery import baker

    from bpp.models import Autor

    baker.make(
        Autor, nazwisko="Nowak", aktualna_jednostka=jednostka, tytul=tytul,
        _quantity=2,
    )

    res = redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "autor",
            "query": 'nazwisko = "Nowak"',
            "postac": "pivot",
            "pivot_row": "jednostka",
            "pivot_col": "tytul",
            "pivot_val": "liczba_autorow",
        },
    )

    assert res.status_code == 200
    assert res.context["pivot"].grand_total == 2


@pytest.mark.django_db
def test_pivot_autorow_eksport_csv(redaktor, jednostka):
    from model_bakery import baker

    from bpp.models import Autor

    baker.make(Autor, nazwisko="Nowak", aktualna_jednostka=jednostka)

    res = redaktor.get(
        reverse("bpp:zapytanie_eksport", kwargs={"export_format": "csv"}),
        {
            "model": "autor",
            "query": 'nazwisko = "Nowak"',
            "postac": "pivot",
            "pivot_row": "jednostka",
            "pivot_val": "liczba_autorow",
        },
    )

    assert res.status_code == 200
    assert b"RAZEM" in res.content


@pytest.mark.django_db
def test_strona_pokazuje_presety_dla_autora(redaktor):
    res = redaktor.get(reverse("bpp:zapytanie"), {"model": "autor"})
    assert b"Audyt kompletno" in res.content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_zapytanie_pivot.py -k autor -v`
Expected: FAIL

- [ ] **Step 2b: Dopisz `pivot` do listy postaci autorskich**

W `src/bpp/views/zapytanie.py` dodaj `(POSTAC_PIVOT, "tabela krzyżowa")` do
`POSTACIE_AUTOR`. Zadanie 3 celowo zostawiło tam samą postać `rekordy`, bo
pivot dla autorów renderował się wtedy przez partial listy na obiektach
`Autor` (puste wiersze, brak `js_safe_pk`/`opis_bibliograficzny_cache`).

- [ ] **Step 3: Rozgałęź `_pivot_context` po modelu**

```python
    def _pivot_context(self, model_key, queryset):
        if model_key == MODEL_AUTOR:
            from bpp.pivot import autor as rejestr

            row_dim, col_dim, metric = rejestr.parse_pivot_params_autor(
                self.request.GET
            )
            buduj = rejestr.zbuduj_pivot_autora
        else:
            from bpp.pivot import rekord as rejestr

            row_dim, col_dim, metric = rejestr.parse_pivot_params(self.request.GET)
            buduj = rejestr.zbuduj_pivot_rekordu
        ...
```

Dodaj w `bpp/pivot/rekord.py` cienkie `zbuduj_pivot_rekordu(base_qs, row, col,
metric)` = `core.zbuduj_pivot(...)` z modelem `Rekord`, żeby oba rejestry miały
tę samą sygnaturę i widok nie musiał wiedzieć, który silnik wołać.

Wymiary/metryki w kontekście bierz z wybranego rejestru
(`rejestr.DIMENSIONS`, `rejestr.METRICS`).

**Filtrowanie wymiarów po bazie metryki.** Partial iteruje `pivot_dimensions`
i nic nie wie o bazach agregacji, więc **widok podaje już przefiltrowany
słownik** — tylko wymiary dostępne w bazie wybranej metryki:

```python
            dostepne = {
                key: dim
                for key, dim in rejestr.DIMENSIONS.items()
                if dim.expr_dla(metric.baza) is not None
            }
            ctx["pivot_dimensions"] = dostepne
```

Dla rejestru rekordowego `expr` jest stringiem, więc `expr_dla()` zawsze zwraca
ścieżkę i filtr nie usuwa niczego — zachowanie multiseeka bez zmian.

Test tego zachowania (dopisz w tym samym pliku):

```python
@pytest.mark.django_db
def test_metryka_kadrowa_ukrywa_wymiary_publikacyjne(redaktor, autor_jan_nowak):
    res = redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "autor",
            "query": 'nazwisko = "Nowak"',
            "postac": "pivot",
            "pivot_val": "liczba_autorow",
        },
    )
    assert "rok" not in res.context["pivot_dimensions"]
    assert "jednostka" in res.context["pivot_dimensions"]


@pytest.mark.django_db
def test_metryka_slotowa_pokazuje_rok(redaktor, autor_jan_nowak):
    res = redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "autor",
            "query": 'nazwisko = "Nowak"',
            "postac": "pivot",
            "pivot_val": "suma_slotow",
        },
    )
    assert "rok" in res.context["pivot_dimensions"]
    assert "typ_odpowiedzialnosci" not in res.context["pivot_dimensions"]
```

**Kolejność zadań:** ten test wymaga metryk z Task 10 (`suma_slotow`). Jeśli
Task 9 wykonujesz przed Task 10, oznacz drugi test `@pytest.mark.xfail(
reason="metryki bazy U dochodzą w Task 10", strict=False)` i zdejmij marker
w Task 10.

- [ ] **Step 4: To samo w eksporcie**

`_eksport_pivota` dostaje `model_key` i wybiera rejestr tą samą logiką.
Wydziel helper `wybierz_rejestr_pivota(model_key)` w `bpp/pivot/__init__.py`,
żeby widok i eksport nie miały dwóch kopii tego `if`-a:

```python
def wybierz_rejestr_pivota(model_key):
    """Rejestr pivota dla modelu przeszukiwanego na stronie zapytania."""
    if model_key == "autor":
        from . import autor

        return autor
    from . import rekord

    return rekord
```

Oba rejestry muszą wystawiać: `DIMENSIONS`, `METRICS`, `parse_params(GET)`,
`zbuduj(base_qs, row, col, metric)` — dorób te dwa aliasy w obu modułach, żeby
interfejs był jednolity.

- [ ] **Step 5: Presety w szablonie**

W `ZapytanieView.get_context_data` dołóż presety dla modelu autor:

```python
PIVOT_PRESETY_AUTOR = (
    ("Struktura kadrowa", "jednostka", "tytul", "liczba_autorow"),
    ("Audyt kompletności ORCID", "jednostka", "ma_orcid", "liczba_autorow"),
    ("Gotowość do PBN", "jednostka", "ma_pbn_uid", "liczba_autorow"),
    ("Struktura płci wg tytułów", "tytul", "plec", "liczba_autorow"),
)
```

W szablonie, w sekcji pomocy, wyrenderuj je jako linki dokładające
`&postac=pivot&pivot_row=…&pivot_col=…&pivot_val=…` do bieżącego zapytania.

- [ ] **Step 6: Run tests**

Run: `uv run pytest src/bpp/tests/test_zapytanie_pivot.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
uv run ruff format src/bpp/ && uv run ruff check src/bpp/views/ src/bpp/pivot/
git add src/bpp/views/ src/bpp/pivot/ src/bpp/templates/bpp/zapytanie.html \
        src/bpp/tests/test_zapytanie_pivot.py
git commit -m "feat(zapytanie): tabela krzyżowa autorów w UI + presety"
```

---

## FAZA 4 — bazy P/U + eksport autorów

### Task 10: metryki bibliometryczne (bazy P i U)

**Files:**
- Modify: `src/bpp/pivot/autor.py` (metryki + wymiary publikacyjne)
- Test: `src/bpp/tests/test_pivot_autor.py` (dopisz)

**WYMÓG DODANY PO ZADANIU 8 — dwa testy, które MUSZĄ tu powstać, bo w bazie
K nie dało się ich postawić:**

1. **Test dedupu, który BEZ dedupu pada.** W bazie K dedup przez świeży
   queryset (`Autor.objects.filter(pk__in=...)` w `zbuduj_pivot_autora`) jest
   redundantny — metryka to `Count(pk, distinct=True)`, a DISTINCT w agregacie
   sam zwija wiersze zwielokrotnione JOIN-em. Sprawdzone empirycznie: po
   usunięciu linii dedupu cała suita `test_pivot_autor.py` (7 testów) nadal
   przechodziła. Dedup staje się nośny WYŁĄCZNIE dla metryk Σ — `Sum` nie ma
   jak rozpoznać duplikatu wiersza. Dlatego test bazy U (np. `suma_slotow`)
   z autorem mającym DWA wiersze `Autor_Jednostka` (dwa nienakładające się
   okresy — model ma `UniqueConstraint` dla wpisów bez daty i
   `ExclusionConstraint` dla datowanych) i filtrem po `autor_jednostka__jednostka`
   MUSI dać poprawną sumę, a po zakomentowaniu dedupu MUSI paść. **Pokaż oba
   przebiegi w raporcie** — bez tego dedup pozostaje nieudowodniony w całym
   rejestrze autorskim.

2. **Test odrzucania wymiaru niedostępnego w bieżącej bazie.**
   `test_parse_params_nieznany_wymiar_wraca_do_domyslnego` sprawdza dziś tylko
   fallback NIEZNANEGO klucza — bo w bazie K wszystkie 12 wymiarów są dostępne,
   więc ścieżki `expr_dla(baza) is None` nie da się wywołać. Gdy dołożysz
   wymiary publikacyjne (`rok`, `dyscyplina`, …) z `expr` jako słownikiem per
   baza, dopisz test: `pivot_row=rok` przy metryce bazy K (`liczba_autorow`)
   musi wrócić do `DEFAULT_ROW`, a przy metryce bazy P/U — zostać przyjęty.
   To jest właściwy test seamu `baza`, obiecany w docstringu tamtego testu.

**Interfaces:**
- Produces: nowe klucze w `METRICS`: `liczba_prac` (baza P,
  `distinct_field="autorzy__rekord_id"`), `suma_slotow` (baza U,
  `field="cache_punktacja_autora_query__slot"`), `suma_pkdaut` (baza U,
  `field="cache_punktacja_autora_query__pkdaut"`); nowe wymiary `rok`,
  `dyscyplina`, `jednostka_pracy`, `typ_odpowiedzialnosci`,
  `charakter_formalny` z `expr` per baza.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.django_db
def test_baza_prac_liczy_prace_autora(
    autor_jan_nowak, jednostka, wydawnictwo_ciagle, wydawnictwo_zwarte
):
    from bpp.models import Autor
    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)
    wydawnictwo_zwarte.dodaj_autora(autor_jan_nowak, jednostka)

    wynik = zbuduj_pivot_autora(
        Autor.objects.all(), DIMENSIONS["autor"], None, METRICS["liczba_prac"]
    )

    assert wynik.grand_total == 2


@pytest.mark.django_db
def test_baza_prac_autor_x_rok(autor_jan_nowak, jednostka, wydawnictwo_ciagle):
    from bpp.models import Autor
    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)

    wynik = zbuduj_pivot_autora(
        Autor.objects.all(),
        DIMENSIONS["autor"],
        DIMENSIONS["rok"],
        METRICS["liczba_prac"],
    )

    assert [label for _, label in wynik.cols] == [str(wydawnictwo_ciagle.rok)]


@pytest.mark.django_db
def test_autorzy_bez_dorobku_nie_zapychaja_macierzy(jednostka):
    from model_bakery import baker

    from bpp.models import Autor
    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    baker.make(Autor, aktualna_jednostka=jednostka, _quantity=3)

    wynik = zbuduj_pivot_autora(
        Autor.objects.all(), DIMENSIONS["jednostka"], None, METRICS["liczba_prac"]
    )

    assert wynik.rows == []
    assert wynik.grand_total == 0


@pytest.mark.django_db
def test_baza_udzialow_sumuje_sloty(autor_jan_nowak, jednostka, dyscyplina1):
    from model_bakery import baker

    from bpp.models import Autor
    from bpp.models.cache import Cache_Punktacja_Autora
    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    baker.make(
        Cache_Punktacja_Autora,
        autor=autor_jan_nowak,
        jednostka=jednostka,
        dyscyplina=dyscyplina1,
        slot="0.5000",
        pkdaut="20.0000",
        rekord_id=[1, 1],
    )

    wynik = zbuduj_pivot_autora(
        Autor.objects.all(), DIMENSIONS["autor"], None, METRICS["suma_slotow"]
    )

    assert float(wynik.grand_total) == pytest.approx(0.5)


@pytest.mark.django_db
def test_wymiar_niedostepny_w_bazie_udzialow():
    from bpp.pivot.autor import DIMENSIONS, BAZA_UDZIALY

    assert DIMENSIONS["typ_odpowiedzialnosci"].expr_dla(BAZA_UDZIALY) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_pivot_autor.py -k "baza_prac or udzial or dorobku or niedostepny" -v`
Expected: FAIL — `KeyError: 'liczba_prac'`

- [ ] **Step 3: Dodaj metryki i wymiary publikacyjne**

W `bpp/pivot/autor.py`:

```python
METRICS: dict[str, PivotMetric] = {
    "liczba_autorow": PivotMetric(
        "liczba_autorow", "Liczba autorów", None, baza=BAZA_KADROWA,
        distinct_field="pk",
    ),
    "liczba_prac": PivotMetric(
        "liczba_prac", "Liczba prac", None, baza=BAZA_PRACE,
        distinct_field="autorzy__rekord_id",
    ),
    "suma_slotow": PivotMetric(
        "suma_slotow", "Σ slotów",
        "cache_punktacja_autora_query__slot", baza=BAZA_UDZIALY,
    ),
    "suma_pkdaut": PivotMetric(
        "suma_pkdaut", "Σ pkdaut (punkty autora)",
        "cache_punktacja_autora_query__pkdaut", baza=BAZA_UDZIALY,
    ),
}
```

Wymiary publikacyjne (dołóż do `DIMENSIONS`):

```python
    "rok": PivotDimension(
        "rok",
        "Rok publikacji",
        {
            BAZA_PRACE: "autorzy__rekord__rok",
            BAZA_UDZIALY: "cache_punktacja_autora_query__rekord__rok",
        },
    ),
    "dyscyplina": PivotDimension(
        "dyscyplina",
        "Dyscyplina pracy",
        {
            BAZA_PRACE: "autorzy__dyscyplina_naukowa_id",
            BAZA_UDZIALY: "cache_punktacja_autora_query__dyscyplina_id",
        },
        label_kind="fk",
        fk_model="bpp.Dyscyplina_Naukowa",
    ),
    "jednostka_pracy": PivotDimension(
        "jednostka_pracy",
        "Jednostka przy pracy",
        {
            BAZA_PRACE: "autorzy__jednostka_id",
            BAZA_UDZIALY: "cache_punktacja_autora_query__jednostka_id",
        },
        allow_column=False,
        label_kind="fk",
        fk_model="bpp.Jednostka",
    ),
    "typ_odpowiedzialnosci": PivotDimension(
        "typ_odpowiedzialnosci",
        "Typ odpowiedzialności",
        {BAZA_PRACE: "autorzy__typ_odpowiedzialnosci_id"},
        label_kind="fk",
        fk_model="bpp.Typ_Odpowiedzialnosci",
    ),
    "charakter_formalny": PivotDimension(
        "charakter_formalny",
        "Charakter formalny pracy",
        {BAZA_PRACE: "autorzy__rekord__charakter_formalny_id"},
        label_kind="fk",
        fk_model="bpp.Charakter_Formalny",
    ),
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest src/bpp/tests/test_pivot_autor.py -v`
Expected: PASS (12 testów)

- [ ] **Step 5: Commit**

```bash
uv run ruff format src/bpp/pivot/autor.py src/bpp/tests/test_pivot_autor.py
uv run ruff check src/bpp/pivot/autor.py src/bpp/tests/test_pivot_autor.py
git add src/bpp/pivot/autor.py src/bpp/tests/test_pivot_autor.py
git commit -m "feat(pivot): metryki bibliometryczne autorów (liczba prac, Σ slotów, Σ pkdaut)"
```

---

### Task 11: eksport autorów CSV/XLSX

**Files:**
- Modify: `src/bpp/views/multiseek_export.py` (funkcje eksportu autorów)
- Modify: `src/bpp/views/zapytanie_export.py` (usuń bramkę „tylko rekordy")
- Test: `src/bpp/tests/test_zapytanie_export.py` (dopisz)

**Interfaces:**
- Produces: `AUTOR_EXPORT_HEADERS`, `AUTOR_EXPORT_XLSX_HEADERS`,
  `autor_csv_export_response(queryset, request, report_title)`,
  `autor_xlsx_export_response(queryset, request, report_title)`,
  `_metryki_dorobku(autor_ids) -> dict[int, tuple[int, Decimal, Decimal]]`.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.django_db
def test_eksport_autorow_csv_ma_kolumny_dorobku(redaktor, autor_jan_nowak):
    res = redaktor.get(
        reverse("bpp:zapytanie_eksport", kwargs={"export_format": "csv"}),
        {"model": "autor", "query": 'nazwisko = "Nowak"'},
    )

    assert res.status_code == 200
    assert b"liczba_prac" in res.content
    assert b"suma_slotow" in res.content
    assert b"Nowak" in res.content


@pytest.mark.django_db
def test_eksport_autorow_nie_zawyza_metryk(
    redaktor, autor_jan_nowak, jednostka, wydawnictwo_ciagle, wydawnictwo_zwarte,
    dyscyplina1,
):
    """Dwa JOIN-y do relacji do-wielu w jednym annotate zawyżyłyby sumy."""
    from model_bakery import baker

    from bpp.models.cache import Cache_Punktacja_Autora

    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)
    wydawnictwo_zwarte.dodaj_autora(autor_jan_nowak, jednostka)
    for rekord_id in ([1, 1], [1, 2]):
        baker.make(
            Cache_Punktacja_Autora,
            autor=autor_jan_nowak,
            jednostka=jednostka,
            dyscyplina=dyscyplina1,
            slot="0.5000",
            pkdaut="10.0000",
            rekord_id=rekord_id,
        )

    res = redaktor.get(
        reverse("bpp:zapytanie_eksport", kwargs={"export_format": "csv"}),
        {"model": "autor", "query": 'nazwisko = "Nowak"'},
    )

    import csv
    import io
    from decimal import Decimal

    wiersze = list(csv.reader(io.StringIO(res.content.decode())))
    naglowek, dane = wiersze[0], wiersze[1]
    kol = dict(zip(naglowek, dane))

    # Bez rozdzielenia agregatów na dwa zapytania wyszłoby 4 prace i Σ slotów
    # 2.0 (praca × wpis punktacji), bo oba JOIN-y mnożą się wzajemnie.
    assert int(kol["liczba_prac"]) == 2
    assert Decimal(kol["suma_slotow"]) == Decimal("1.0000")
    assert Decimal(kol["suma_pkdaut"]) == Decimal("20.0000")


@pytest.mark.django_db
def test_eksport_autorow_xlsx(redaktor, autor_jan_nowak):
    res = redaktor.get(
        reverse("bpp:zapytanie_eksport", kwargs={"export_format": "xlsx"}),
        {"model": "autor", "query": 'nazwisko = "Nowak"'},
    )

    assert "spreadsheetml" in res["Content-Type"]


@pytest.mark.django_db
def test_eksport_autorow_html_400(redaktor, autor_jan_nowak):
    res = redaktor.get(
        reverse("bpp:zapytanie_eksport", kwargs={"export_format": "html"}),
        {"model": "autor", "query": 'nazwisko = "Nowak"'},
    )

    assert res.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_zapytanie_export.py -k autorow -v`
Expected: FAIL — 400 „Eksport autorów zostanie dodany w kolejnym kroku."

- [ ] **Step 3: Implementacja w `multiseek_export.py`**

```python
AUTOR_EXPORT_HEADERS = (
    "nazwisko",
    "imiona",
    "tytul",
    "stopien_sluzbowy",
    "jednostka",
    "funkcja",
    "orcid",
    "orcid_w_pbn",
    "pbn_uid_id",
    "email",
    "id_kadrowy",
    "plec",
    "liczba_prac",
    "suma_slotow",
    "suma_pkdaut",
    "id_autora",
    "link_do_bpp_url",
)

AUTOR_EXPORT_XLSX_HEADERS = (
    "Nazwisko",
    "Imiona",
    "Tytuł",
    "Stopień służbowy",
    "Jednostka",
    "Funkcja",
    "ORCID",
    "ORCID w PBN",
    "PBN UID",
    "E-mail",
    "ID kadrowy",
    "Płeć",
    "Liczba prac",
    "Σ slotów",
    "Σ pkdaut",
    "ID autora",
    "Link do BPP",
)

AUTOR_EXPORT_SELECT_RELATED = (
    "tytul",
    "stopien_sluzbowy",
    "aktualna_jednostka",
    "aktualna_funkcja",
    "plec",
)


def _metryki_dorobku(autor_ids):
    """Liczba prac, Σ slotów i Σ pkdaut dla podanych autorów.

    DWA zapytania, nie jedno: Count(distinct) idzie przez bpp_autorzy_mat,
    a Sum(slot/pkdaut) przez bpp_cache_punktacja_autora. Dwie różne relacje
    „do wielu" w jednym annotate() mnożą wiersze przed agregacją i sumy
    wychodzą zawyżone (praca × wpis punktacji).
    """
    from django.db.models import Count, Sum

    from bpp.models import Autor

    prace = {
        row["pk"]: row["n"]
        for row in Autor.objects.filter(pk__in=autor_ids)
        .values("pk")
        .annotate(n=Count("autorzy__rekord_id", distinct=True))
    }
    udzialy = {
        row["pk"]: (row["slot"], row["pkdaut"])
        for row in Autor.objects.filter(pk__in=autor_ids)
        .values("pk")
        .annotate(
            slot=Sum("cache_punktacja_autora_query__slot"),
            pkdaut=Sum("cache_punktacja_autora_query__pkdaut"),
        )
    }
    return {
        pk: (
            prace.get(pk, 0),
            udzialy.get(pk, (None, None))[0],
            udzialy.get(pk, (None, None))[1],
        )
        for pk in set(prace) | set(udzialy)
    }


def _iter_autor_export_rows(queryset, request):
    queryset = queryset.select_related(*AUTOR_EXPORT_SELECT_RELATED)
    autorzy = list(queryset)
    metryki = _metryki_dorobku([a.pk for a in autorzy])
    for autor in autorzy:
        liczba_prac, slot, pkdaut = metryki.get(autor.pk, (0, None, None))
        yield (
            _export_value(autor.nazwisko),
            _export_value(autor.imiona),
            _export_value(autor.tytul),
            _export_value(autor.stopien_sluzbowy),
            _export_value(autor.aktualna_jednostka),
            _export_value(autor.aktualna_funkcja),
            _export_value(autor.orcid),
            _export_value(autor.orcid_w_pbn),
            _export_value(autor.pbn_uid_id),
            _export_value(autor.email),
            _export_value(autor.system_kadrowy_id),
            _export_value(autor.plec),
            liczba_prac,
            _export_value(slot),
            _export_value(pkdaut),
            autor.pk,
            request.build_absolute_uri(autor.get_absolute_url()),
        )
```

`autor_csv_export_response` — jak `csv_export_response`, ale z
`AUTOR_EXPORT_HEADERS` i `_iter_autor_export_rows`.
`autor_xlsx_export_response` — jak `xlsx_export_response` wariant „dane", ale
nagłówki autorskie, `freeze="B1"`, format `0.0000` na kolumnach „Σ slotów"
i „Σ pkdaut", hiperlink na „Link do BPP", tabela o nazwie `AutorExport`.

W `zapytanie_export.py` usuń bramkę `model_key != MODEL_REKORD` i dodaj:

```python
        if model_key == MODEL_AUTOR:
            if export_format not in DATA_FORMATS:
                return HttpResponseBadRequest(
                    "Eksport autorów dostępny jako CSV albo XLSX."
                )
            if export_format == "csv":
                return autor_csv_export_response(queryset, request, report_title)
            return autor_xlsx_export_response(queryset, request, report_title)
```

(po sprawdzeniu capa danych i po rozgałęzieniu pivota).

- [ ] **Step 3b: Przywróć pasek eksportu dla autorów**

W `src/bpp/views/zapytanie.py`, w `eksport_formaty`, gałąź dla
`MODEL_AUTOR` zwraca dziś pustą krotkę — zadanie 5 celowo tak zrobiło, bo
backend 400-ował każdy format dla autora i pasek pokazywałby martwe linki.
Po tym zadaniu eksport autorów działa, więc gałąź ma zwracać
`(("csv", "CSV"), ("xlsx", "XLSX"))`. Dopisz test, że pasek renderuje się
na `/zapytanie/?model=autor` z linkiem do `/zapytanie/eksport/csv/`.

- [ ] **Step 4: Run tests**

Run: `uv run pytest src/bpp/tests/test_zapytanie_export.py -v`
Expected: PASS (wszystkie, w tym 4 nowe)

- [ ] **Step 5: Commit**

```bash
uv run ruff format src/bpp/views/ src/bpp/tests/test_zapytanie_export.py
uv run ruff check src/bpp/views/ src/bpp/tests/test_zapytanie_export.py
git add src/bpp/views/ src/bpp/tests/test_zapytanie_export.py
git commit -m "feat(zapytanie): eksport autorów CSV/XLSX z metrykami dorobku"
```

---

### Task 12: test Playwright, newsfragmenty, dokumentacja

**Files:**
- Modify: `src/bpp/tests/test_playwright/test_multiseek_djangoql.py`
- Create: `src/bpp/newsfragments/zapytanie-pivot-autorow.feature.rst`
- Modify: `docs/` — jeśli istnieje strona o wyszukiwaniu zapytaniem, dopisz
  sekcję o postaciach i eksportach (sprawdź:
  `grep -rl "zapytaniem" docs/`)

- [ ] **Step 1: Warunki wstępne Playwrighta**

```bash
make assets
make playwright-install
```

- [ ] **Step 2: Dopisz test przeglądarkowy**

```python
def test_zapytanie_przelaczanie_postaci(page, live_server, admin_user):
    """Wybór postaci wyniku jedzie razem z zapytaniem przez formularz GET."""
    page.goto(f"{live_server.url}/zapytanie/?model=rekord&query=rok+%3E%3D+2000")
    page.select_option("#id_postac", "list")
    page.click("button[type=submit]")
    page.wait_for_selector(".multiseek-list-report")
    assert "postac=list" in page.url
```

(Dostosuj do istniejących fixture'ów w pliku — sprawdź, jak logowany jest user
w pozostałych testach tego modułu i użyj tego samego mechanizmu.)

- [ ] **Step 3: Uruchom test Playwrighta**

Run: `uv run pytest src/bpp/tests/test_playwright/test_multiseek_djangoql.py -v`
Expected: PASS (pierwszy przebieg może timeoutować na zimnym starcie — ponów)

- [ ] **Step 4: Newsfragment**

`src/bpp/newsfragments/zapytanie-pivot-autorow.feature.rst`:

```rst
Wyszukiwanie zapytaniem pozwala teraz zbudować tabelę krzyżową także dla
autorów — w wymiarach kadrowych (jednostka, tytuł, stopień, funkcja, płeć,
kompletność ORCID/PBN/e-mail) oraz bibliometrycznych (liczba prac, suma
slotów, suma punktów autora wg roku i dyscypliny). Kartotekę autorów wraz
z metrykami dorobku można wyeksportować do CSV i XLSX.
```

- [ ] **Step 5: Pełna suita bez Playwrighta**

Run: `make tests-without-playwright`
Expected: PASS. Jeśli coś pada — napraw, nie pomijaj.

- [ ] **Step 6: pre-commit**

Run: `uv run pre-commit`
(bez argumentów!). Błędy poprawiaj ręcznie Editem, nigdy `ruff check --fix`.

- [ ] **Step 7: Commit**

```bash
git add src/bpp/tests/test_playwright/ src/bpp/newsfragments/ docs/
git commit -m "test(zapytanie): test Playwright postaci wyniku + newsfragmenty"
```

---

## Weryfikacja końcowa (przed PR-em)

- [ ] `uv run pytest src/bpp/tests/test_zapytanie*.py src/bpp/tests/test_pivot_autor.py -q` — zielone
- [ ] `uv run pytest src/bpp/tests/test_multiseek_pivot.py src/bpp/tests/test_multiseek_pivot_view.py -q` — **25 passed, zero zmian w tych plikach** (`git diff --stat` ich nie pokazuje)
- [ ] `make tests-without-playwright` — zielone
- [ ] `uv run pytest src/bpp/tests/test_playwright/ -q` — zielone
- [ ] `uv run pre-commit` — czysto
- [ ] `git diff dev --stat` — brak zmian w `src/*/migrations/`
- [ ] Newsfragmenty istnieją w `src/bpp/newsfragments/` (nie w `changes/`)
