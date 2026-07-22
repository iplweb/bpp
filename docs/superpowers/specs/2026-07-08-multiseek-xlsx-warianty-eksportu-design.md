# Multiseek — dwa warianty eksportu XLSX (Źródło/Typ MNiSW/MEiN + „opis bibliograficzny")

Data: 2026-07-08
Zgłoszenie: Freshdesk #373 („Rezultat wyszukiwania — export do excel", Ewa Matczuk)
Status: zaakceptowany zarys, do przełożenia na plan implementacji.

## 1. Problem

Multiseek ma dziś **jeden** eksport XLSX/CSV (`MyMultiseekExport`
w `src/bpp/views/mymultiseek.py`) — układ **kolumnowy** (jedna dana na kolumnę:
Tytuł, Autorzy, Rok, IF, PK, identyfikatory, linki). Klientka prosi o dwie
rzeczy:

1. **Wzbogacić istniejący eksport** o dwie kolumny: `Źródło`
   i `Typ MNiSW/MEiN`.
2. **Dodać drugi wariant** eksportu, w którym cały opis bibliograficzny jest
   w **jednej** kolumnie, a po nim kolumny: `IF`, `PK`, `Charakter`,
   `Typ MNiSW/MEiN` (odpowiednik ekranowego raportu „lista").

Decyzja projektowa: **NIE** scalać obu układów w jeden arkusz („wszystkie
kolumny naraz") — to dublowałoby dane (Autorzy/Źródło/Tytuł są już zawarte
w „Opis bibliograficzny"), dawało szeroki, nieczytelny arkusz i ignorowało
intencję Klientki, która sama prosi o „drugi wariant". Zamiast tego: **dwa
odrębne, wąskie warianty**, każdy pod swój cel.

## 2. Dwa warianty

### Wariant `dane` (obecny układ, wzbogacony — realizuje prośbę #1)

Układ kolumnowy. **Czysta insercja** dwóch nowych kolumn — `Źródło` tuż po
`Autorzy`, `Typ MNiSW/MEiN` tuż po `Typ rekordu` — bez zmiany wzajemnej
kolejności dotychczasowych kolumn (w szczególności `BPP ID` **zostaje** przed
`Typ rekordu`, gdzie jest dziś). Dzięki temu istniejący układ CSV nie łamie
się dla ewentualnych konsumentów downstream; jedyna zmiana to dwie nowe
kolumny wsunięte w środek i związane z nią przesunięcie indeksów kolumn-linków
o **dwie** pozycje (patrz §4). Docelowa kolejność nagłówków:

| # | Nagłówek XLSX | Nagłówek CSV (ASCII) | Źródło danych (`Rekord`) |
|---|---|---|---|
| 1 | Tytuł oryginalny | `tytul_oryginalny` | `tytul_oryginalny` |
| 2 | Autorzy | `autorzy` | `opis_bibliograficzny_zapisani_autorzy_cache` |
| 3 | **Źródło** | **`zrodlo`** | `zrodlo.nazwa` (FK `Zrodlo`, nullable → `""`) |
| 4 | Rok | `rok` | `rok` |
| 5 | Impact Factor | `impact_factor` | `impact_factor` |
| 6 | PK | `pk` | `punkty_kbn` |
| 7 | BPP ID | `bpp_id` | `str(tuple(pk))` |
| 8 | Typ rekordu | `typ_rekordu` | `describe_content_type` |
| 9 | **Typ MNiSW/MEiN** | **`typ_mnisw_mein`** | `typ_kbn.nazwa` (nullable → `""`) |
| 10 | ID rekordu | `id_rekordu` | `object_id` |
| 11 | PBN UID | `pbn_uid_id` | `pbn_uid_id` |
| 12 | Link do BPP | `link_do_bpp_url` | `get_absolute_url()` (absolutny) |
| 13 | Link do edycji w BPP | `link_do_bpp_admin_url` | `_admin_change_url()` |
| 14 | Link do PBN | `link_do_pbn_url` | `_pbn_publication_url()` |

Uwaga o „nazwie":
- `Typ_KBN` i `Charakter_Formalny` dziedziczą po `NazwaISkrot`, którego
  `__str__` zwraca `nazwa` — więc `str(obj)` == `obj.nazwa`.
- `Zrodlo` **nie** dziedziczy po `NazwaISkrot`; ma własne pola `nazwa`/`skrot`
  i własny `__str__`, który **dopisuje `poprzednia_nazwa`** (`zrodlo.py:202-211`).
Dlatego dla źródła preferujemy jawne `zrodlo.nazwa` (a nie `str(zrodlo)`) —
`str()` czytałoby `poprzednia_nazwa`, kolejny deferred field → dodatkowe
zapytanie przy `.only()`. Patrz wymagania `select_related`/`only` w §4.

Wariant `dane` obowiązuje **zarówno CSV jak i XLSX** — obie ścieżki dzielą
wspólny builder wierszy, więc dwie nowe kolumny wchodzą do obu naraz. CSV
używa nagłówków ASCII snake_case (kolumna wyżej), XLSX — polskich etykiet.

### Wariant `opis` (nowy — realizuje prośbę #2)

Układ raportowy, **tylko XLSX**. Sześć kolumn:

| # | Nagłówek XLSX | Źródło danych (`Rekord`) |
|---|---|---|
| 1 | Lp. | licznik wiersza (1..N) |
| 2 | Opis bibliograficzny | `opis_bibliograficzny_cache` |
| 3 | IF | `impact_factor` |
| 4 | PK | `punkty_kbn` |
| 5 | Charakter | `charakter_formalny.nazwa` (nullable → `""`) |
| 6 | Typ MNiSW/MEiN | `typ_kbn.nazwa` (nullable → `""`) |

Uwaga: `opis_bibliograficzny_cache` bywa HTML-em (kursywa w tytule źródła,
`<br>`, `<div>` itp.). Do komórki XLSX wchodzi **czysty tekst**. Potrzebny
**dedykowany helper** `_plain_opis_bibliograficzny(html_str)` — NIE reużywać
`_plain_multiseek_report_title` w całości, bo ono ma fallback na
„Rezultat wyszukiwania" dla pustego wejścia (wstrzyknąłby domyślny tytuł do
komórek z pustym opisem). Sekwencja helpera, w tej kolejności:
1. zamiana tagów blokowych na spację (`MULTISEEK_REPORT_TITLE_HTML_BREAK_RE`
   — istniejące regex, żeby `<br>`/`<div>` nie sklejały słów),
2. `strip_tags`,
3. `html.unescape`,
4. `_single_line_text` (kolaps białych znaków),
5. **bez** fallbacku — puste wejście → `""`.
Helper zwraca czysty tekst; **nie** woła `sanitize_xlsx_cell` sam — builder
odpowiedzi XLSX i tak przepuszcza każdy wiersz przez `sanitize_xlsx_row`
(`mymultiseek.py:357`), więc sanityzacja formuł dzieje się raz, w jednym
miejscu (unikamy podwójnej warstwy).

## 3. Routing

URL bez zmian:
`^multiseek/export/(?P<export_format>[\w-]+)/$` → `MyMultiseekExport`.

Wariant wybieramy query-paramem **`wariant`** (`dane` | `opis`,
domyślnie `dane`). Każdy link w dropdownie to statyczny `href` — pobieranie
nie wymaga JS-a:

- CSV → `…/multiseek/export/csv/`
- XLS: dane → `…/multiseek/export/xlsx/`
- XLS: opis → `…/multiseek/export/xlsx/?wariant=opis`

Walidacja w widoku:

- `export_format ∉ {csv, xlsx}` → `HttpResponseBadRequest` (jak dziś).
- `wariant ∉ {dane, opis}` → potraktuj jak `dane` (defensywnie, bez 400 —
  nieznany wariant nie jest błędem klienta wartym twardej odmowy).
- `wariant == opis` przy `export_format == csv` → **degraduje do `dane`**
  (opis to format czytelny/raportowy; CSV opisu nie zamawiano — YAGNI).

Parametr `print-removed` współistnieje z `wariant` (oba jako query-params) —
istniejące `{% if print_removed %}?print-removed=1{% endif %}` w szablonie
trzeba uogólnić na łączenie dwóch parametrów (patrz §5).

## 4. Refactor: wydzielenie logiki eksportu

`src/bpp/views/mymultiseek.py` ma ~488 linii i dokładamy drugi zestaw
nagłówków + iterator + formatowanie XLSX. Wydzielamy **całą logikę eksportu**
do nowego modułu `src/bpp/views/multiseek_export.py`, zostawiając widok
cienki (routing + walidacja + wybór wariantu).

### Do `multiseek_export.py` przenosimy (i rozszerzamy):

Stałe nagłówków / pól:
- `MULTISEEK_EXPORT_HEADERS`, `MULTISEEK_EXPORT_XLSX_HEADERS`
  (rozszerzone o Źródło + Typ MNiSW/MEiN),
- **nowe**: `MULTISEEK_EXPORT_OPIS_XLSX_HEADERS`,
- `MULTISEEK_EXPORT_FIELDS` — rozbić na `..._DANE_FIELDS`
  i `..._OPIS_FIELDS` (różne `.only(...)`; szczegóły + krytyczna kwestia
  `select_related` niżej). **Uwaga**: obecne `MULTISEEK_EXPORT_FIELDS`
  (`mymultiseek.py:74-82`) zawiera `opis_bibliograficzny_zapisani_autorzy_cache`
  (kolumna „Autorzy" wariantu `dane`), a **nie** `opis_bibliograficzny_cache`.
  Wariant `opis` renderuje `opis_bibliograficzny_cache` — jego lista `only()`
  **musi jawnie** zawierać `opis_bibliograficzny_cache` (i nie potrzebuje
  `..._zapisani_autorzy_cache`). Skopiowanie bazowej listy „w ciemno" zostawi
  `opis_bibliograficzny_cache` jako deferred → N+1 przy 5000 wierszy, dokładnie
  to, przed czym broni sekcja niżej,
- helpery: `_export_value`, `_single_line_text`, `_sanitize_spreadsheet_*`,
  `_pbn_publication_url`, `_admin_change_url`, `_export_filename`,
  `_xlsx_worksheet_title`, `_plain_multiseek_report_title` i pokrewne
  (albo import z jednego miejsca — nie duplikować).

Buildery wierszy (dwa, zamiast rozgałęzień w jednym):
- `iter_export_rows_dane(queryset, request)` — obecny `_iter_export_rows`
  + dwie nowe kolumny we właściwych pozycjach,
- `iter_export_rows_opis(queryset, request)` — `enumerate(…, start=1)` dla Lp.,
  `opis_bibliograficzny_cache` przez strip_tags/unescape.

Buildery odpowiedzi:
- `csv_export_response(queryset, request, report_title)` — zawsze `dane`,
- `xlsx_export_response(queryset, request, report_title, wariant)` — wybiera
  nagłówki + iterator + reguły formatowania wg wariantu.

### Zapytanie — `select_related` obowiązkowe (inaczej N+1 przy 5000 wierszy)

**Krytyczne.** Obecny widok w `MyMultiseekExport.get` (`mymultiseek.py:416`)
robi `queryset.select_related(None).only(*MULTISEEK_EXPORT_FIELDS)` — to
**zdejmuje** `select_related` ustawiony wcześniej w `get_queryset`. Jeśli w tym
stanie sięgniemy po `rekord.zrodlo.nazwa` / `rekord.typ_kbn.nazwa` /
`rekord.charakter_formalny.nazwa`, każdy wiersz odpali osobne zapytanie — przy
`MULTISEEK_EXPORT_MAX_ROWS = 5000` to tysiące zapytań na jeden eksport.

Dlatego builder odpowiedzi musi ustawić `select_related` **per wariant** i
odpowiednie `only(...)` po polach relacji:

- wariant `dane`: `select_related("zrodlo", "typ_kbn")`,
  `only(..., "zrodlo__nazwa", "zrodlo__poprzednia_nazwa", "typ_kbn__nazwa")`
  — `zrodlo__poprzednia_nazwa` jest konieczne, bo `Zrodlo.__str__` je czyta;
  jeśli użyjemy jawnie `zrodlo.nazwa` (rekomendowane, §2) i **nie** wołamy
  `str(zrodlo)`, wtedy `zrodlo__poprzednia_nazwa` można pominąć.
- wariant `opis`: `select_related("charakter_formalny", "typ_kbn")`,
  `only("id", "opis_bibliograficzny_cache", "impact_factor", "punkty_kbn",
  "charakter_formalny__nazwa", "typ_kbn__nazwa")` — `opis_bibliograficzny_cache`
  **jawnie** (patrz uwaga wyżej), bez `..._zapisani_autorzy_cache`.

Precedens jest w tym samym pliku: `get_queryset` (`mymultiseek.py:133`) już
robi dokładnie `select_related("charakter_formalny", "typ_kbn")` dla raportów
ekranowych — skopiować ten wzorzec. Uwaga: `.only()` musi listować pola relacji
(`typ_kbn__nazwa`), a nie samo FK (`typ_kbn`), bo samo FK zostawia tylko id.

### Indeksy kolumn — nie hardkodować

`MULTISEEK_EXPORT_XLSX_URL_COLUMNS = (10, 11, 12)` to dziś twarde numery
kolumn z linkami. Po wstawieniu **dwóch** kolumn (`Źródło`, `Typ MNiSW/MEiN`)
linki przesuną się o dwie pozycje (lądują na 12/13/14). Zamiast przepisać
liczby, **wyliczać indeksy z nazw nagłówków**
(nagłówki linków **zaczynają się** od „Link" — więc `startswith("Link")`,
NIE `endswith`; albo jawna mapa nazwa→indeks). openpyxl indeksuje kolumny
**od 1**, a `list.index()` liczy **od 0** — konwersja to `headers.index(name) + 1`.
Analogicznie reguły `number_format` (IF `0.000`, PK `0.00`) — liczyć indeksy
IF/PK z nagłówków, bo w wariancie `opis` siedzą pod innymi numerami niż
w `dane`.

Formatowanie per-wariant:
- `dane`: kolumny-linki → `=HYPERLINK(...)`, `freeze_panes="B1"`, format
  liczb dla IF/PK.
- `opis`: brak kolumn-linków, format liczb dla IF/PK (inne indeksy niż
  w `dane` — liczone z nagłówków), `freeze_panes = "A2"` (zamraża **tylko
  wiersz nagłówka**; celowo NIE „C2"/„B2", które zamroziłyby też szeroką
  kolumnę Opis). Nota: `dane` używa `"B1"`, co zamraża kolumnę A (Tytuł),
  a nie wiersz — to inna semantyka i celowo różna między wariantami.

Obie ścieżki nadal używają `worksheet_columns_autosize`,
`worksheet_create_table`, nagłówkowego fill/font — te helpery zostają
w `bpp/util/xlsx.py` (bez zmian).

## 5. UI — dropdown w `paginator.html`

Plik: `src/django_bpp/templates/multiseek/paginator.html`, blok eksportu
(dziś linie ~32–45, wspólny dla gałęzi `is_live` i nie-`is_live`).

Zamieniamy dwa `<li>` (CSV, XLS) na **jeden** trigger + `dropdown-pane`:

```
[⬇ Eksport ▾]
   ├ ⬇ CSV
   ├ ⬇ XLS: dane
   └ ⬇ XLS: opis bibliograficzny
```

Efekt: widoczny wiersz akcji **skraca się** (dwa elementy → jeden), a wybór
formatu żyje w popoverze (zero kosztu poziomego).

Zależność techniczna: **Foundation Dropdown JS**. Przed implementacją
zweryfikować, czy Foundation JS (`Foundation.Dropdown`/`data-dropdown`) jest
zainicjowany na stronie multiseeka (publiczny frontend). Jeśli tak —
`dropdown-pane` z `data-toggle`. Jeśli nie — **fallback na natywny
`<details>/<summary>`** (zero JS, działa wszędzie), ostylowany pod istniejący
`menu`. Wybór fallbacku nie zmienia niczego w backendzie (linki i tak
statyczne).

Query-params: linki muszą składać `wariant` + ewentualne `print-removed`.
Uogólnić dzisiejsze `{% if print_removed %}?print-removed=1{% endif %}` na
budowę query-stringa z obu parametrów (np. mały pattern łączenia albo
`?wariant=opis{% if print_removed %}&print-removed=1{% endif %}`).

Widoczność bloku bez zmian: `request.user.is_authenticated and
paginator_count > 0 and paginator_count <= multiseek_export_max_rows`.

## 6. Testy

Rozszerzyć `src/bpp/tests/test_views/test_mymultiseek.py`:

1. **`dane` — nowe kolumny**: XLSX zawiera nagłówki `Źródło` i `Typ MNiSW/MEiN`,
   CSV zawiera nagłówki ASCII `zrodlo` i `typ_mnisw_mein` (różne tokeny —
   patrz tabela §2), obie na właściwych pozycjach (czysta insercja, `BPP ID`
   nadal przed `Typ rekordu`). Dla rekordu z przypisanym źródłem/typem wartości
   wypełnione, dla rekordu bez — puste (`""`).
2. **`opis` — układ**: `?wariant=opis` na `xlsx` daje dokładnie 6 kolumn
   w kolejności [Lp., Opis bibliograficzny, IF, PK, Charakter, Typ MNiSW/MEiN];
   opis w jednej komórce; numeracja Lp. rośnie 1..N; HTML w opisie
   wyczyszczony do tekstu.
3. **Degradacja CSV**: `?wariant=opis` na `csv` zwraca układ `dane`
   (opis nie przecieka do CSV).
4. **Nieznany wariant**: `?wariant=cokolwiek` → układ `dane`, status 200.
5. **Regresja indeksów linków**: kolumny-linki w `dane` faktycznie zawierają
   `=HYPERLINK(...)` po przesunięciu przez `Źródło` (łapie pomyłkę
   hardkodowanych numerów).
6. **`print-removed` + `wariant`**: oba parametry współistnieją (eksport
   trybu „usunięte ręcznie" z wariantem).
7. **Query-count (regresja N+1)**: `django_assert_num_queries` (lub
   `CaptureQueriesContext`) nad zestawem wielu wierszy o **różnych** źródłach,
   typach i charakterach — liczba zapytań ograniczona i **nie rośnie z liczbą
   wierszy**. To jedyny strażnik przed cichym powrotem N+1 z §4 (bez niego
   regresja `.only()`/`select_related` przejdzie na zielono). Osobny test dla
   `dane` (zrodlo/typ_kbn) i dla `opis` (charakter_formalny/typ_kbn).

**Uwaga o istniejących testach XLSX**: `test_mymultiseek.py` (obecnie ~254-276)
hardkoduje układ wiersza danych — `worksheet["D2"].number_format == "0.000"`
(IF), `["E2"] == "0.00"` (PK) i pozycje komórek `=HYPERLINK`. Wstawienie
`Źródło` na kolumnę 3 **przesuwa** IF→E, PK→F i linki o dwie pozycje, więc
te asercje **trzeba przepisać** (nie „zachować"). Bez zmian zostają jedynie
asercje sanityzacji formuł (`=`, `+`, `-`, `@`) i limitu
`MULTISEEK_EXPORT_MAX_ROWS`, które nie zależą od pozycji kolumn.

## 7. Newsfragment

`src/bpp/newsfragments/fd373.feature.rst` — krótka nota: eksport wyników
multiseeka do XLSX zyskał kolumny Źródło i Typ MNiSW/MEiN oraz drugi wariant
z opisem bibliograficznym w jednej kolumnie.

## 8. Kolejność implementacji

Sekwencja tak dobrana, by każdy krok był osobno weryfikowalny, a diff
czytelny:

1. **Weryfikacja Foundation Dropdown JS** — sprawdzić (grep/przeglądarka),
   czy `data-dropdown`/`Foundation.Dropdown` działa na stronie multiseeka.
   Wynik determinuje wybór dropdown-pane vs natywny `<details>` w §5. To
   pierwszy, samodzielny krok — nie otwarte pytanie w trakcie kodowania.
2. **Refactor bez zmiany zachowania** — przeniesienie logiki eksportu do
   `src/bpp/views/multiseek_export.py` jako **osobny commit, zielone
   istniejące testy**, zero zmian w kolumnach/wariantach. Dzięki temu review
   oddziela „szum przenoszenia" od logiki.
3. **Wariant `dane` + dwie kolumny** (z `select_related`!) — CSV i XLSX.
4. **Wariant `opis`** — XLSX, helper `_plain_opis_bibliograficzny`, routing
   `?wariant=`.
5. **UI dropdown** w `paginator.html`.
6. **Testy + newsfragment.**

## 9. Poza zakresem (YAGNI)

- Brak wariantu `opis` dla CSV.
- Brak scalonego „mega-arkusza".
- Brak konfigurowalnego wyboru kolumn przez użytkownika.
- Brak zmian w limicie `MULTISEEK_EXPORT_MAX_ROWS` ani w migracjach
  (wszystkie pola już istnieją na `Rekord`).
