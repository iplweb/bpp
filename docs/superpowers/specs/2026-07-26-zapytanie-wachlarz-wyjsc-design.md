# Wachlarz wyjść dla „Wyszukiwania zapytaniem" (DjangoQL)

**Data:** 2026-07-26
**Gałąź:** `feat/zapytanie-wyjscia`
**Worktree:** `~/Programowanie/bpp-zapytanie-wyjscia`

## Problem

Strona „Wyszukiwanie zapytaniem" (`/zapytanie/`, `bpp.views.zapytanie.ZapytanieView`)
umie tylko jedno: pokazać stronicowaną tabelkę *reprezentacja / ID / akcje*. Nie
da się z niej wyeksportować niczego — ani BibTeX-a, ani XLSX-a, ani zrobić tabeli
krzyżowej. Multiseek ma cały ten wachlarz, ale jest przypięty do formularza
w sesji, a DjangoQL jest istotnie bardziej ekspresyjny od formularza (konwersja
formularz → DjangoQL istnieje, odwrotna nie jest wykonalna).

Osobno: dla modelu `Autor` nie istnieje żadna tabela krzyżowa i nie było
oczywistego pomysłu, jakie miałaby mieć wymiary.

Zakres tego dokumentu obejmuje jedno i drugie.

## Rozstrzygnięcia wstępne

1. Postulat „zrobić stronę, gdzie u góry pisze się pytanie, a pod spodem jest
   wynik" jest **już zrealizowany** — to właśnie `/zapytanie/` (GET
   `?model=&query=`, historia zapytań, formatter, „wyjaśnij liczby"). Nie
   powstaje żadna nowa strona; rozbudowujemy istniejącą.
2. Rekordy dostają **pełny parytet z multiseekiem** (postać wyniku + 5 formatów
   eksportu).
3. Autorzy dostają tabelę krzyżową w **obu rodzinach** (kadrowa i
   bibliometryczna), wdrażane fazowo, oraz eksport CSV/XLSX z kartoteką
   **i** metrykami dorobku.

## Architektura

Teza: warstwa wyjścia (eksport, pivot) nie jest funkcją multiseeka — jest
funkcją *querysetu*. Dziś jest zaparkowana pod multiseekiem tylko dlatego, że
multiseek był pierwszym konsumentem. Dokładamy drugie wejście i przesuwamy
granice tam, gdzie należą.

```
                  wejście                          warstwa wyjścia (wspólna)
  ┌──────────────────────────────┐        ┌─────────────────────────────────────┐
  │ formularz multiseek → sesja  │──qs──▶ │ multiseek_export.py                 │
  │ (MyMultiseekResults)         │        │  • csv/xlsx/html/docx/bib           │
  ├──────────────────────────────┤        │  • document_export_response() ←NOWE │
  │ DjangoQL → apply_search      │──qs──▶ │  • autor_csv/xlsx_export_response   │
  │ (wykonaj_zapytanie() ←NOWE)  │        ├─────────────────────────────────────┤
  └──────────────────────────────┘        │ bpp/pivot/  ←NOWY pakiet            │
                                          │  core.py   — macierz, etykiety,     │
                                          │              bramki, strategie      │
                                          │  rekord.py — wymiary Rekordu        │
                                          │  autor.py  — wymiary Autora ←NOWE   │
                                          └─────────────────────────────────────┘
```

### Trzy ekstrakcje w istniejącym kodzie

**E1. `wykonaj_zapytanie(model_key, query)`** — wyjęte z
`ZapytanieView.render_results` (`src/bpp/views/zapytanie.py:366`) do funkcji
modułowej. Zwraca `(queryset, error, error_location)`; `apply_search` +
`.distinct()` + obsługa `DjangoQLError/FieldError/ValidationError/ValueError`
w jednym miejscu. Powód: strona i eksport **muszą** liczyć ten sam queryset.
Dziś logika siedzi w metodzie widoku, więc eksport musiałby ją zdublować
i mógłby się z czasem rozjechać.

**E2. `document_export_response(queryset, request, report_type, report_title,
export_format)`** — wyjęte z `MyMultiseekExport._export_document`
(`src/bpp/views/mymultiseek.py:349`) do `multiseek_export.py`. Metoda nie używa
`self` do niczego poza pobraniem `report_type` (feature envy), więc ekstrakcja
jest mechaniczna. Po niej `MyMultiseekExport._export_document` to 3 linie
delegacji, a strona zapytania woła dokładnie tę samą funkcję — jeden zestaw
partiali, jedna sanityzacja HTML, jedna konwersja do DOCX.

**E3. `bpp/pivot/` jako pakiet.** Zawartość `bpp/multiseek_registry/pivot.py`
rozdzielona na `bpp/pivot/core.py` (generyk: `PivotDimension`, `PivotMetric`,
`PivotResult`, `_build_matrix`, `_labels`, `_format_pk_bucket`,
`PIVOT_MAX_CELLS`, `PIVOT_MAX_PAIRS`, `PivotTooLargeError`, strategie) i
`bpp/pivot/rekord.py` (rejestr wymiarów/metryk Rekordu, `parse_pivot_params`).
`bpp/multiseek_registry/pivot.py` zostaje **cienkim re-eksportem**, żeby nie
tknąć ani jednego call-site'u w szablonach, widokach i testach z #670.
`_dedup_strategy` przestaje importować `Rekord` na sztywno — model bazowy jest
parametrem.

Kryterium poprawności E3: suita testów pivota (`test_multiseek_pivot.py`,
`test_multiseek_pivot_view.py`, 25 testów) przechodzi **bez zmian w plikach
testowych**. To dowód, że przenosiny są semantycznie neutralne.

## Część I — rekordy na `/zapytanie/`

### Postać wyniku

Nowy parametr GET `postac`, mapowany na multiseekowe `report_type`:

| `postac` | render | uwagi |
|---|---|---|
| `rekordy` | dzisiejsza tabela na `bpp/zapytanie.html` | **domyślna**; opis + ID + akcje (Zobacz/Edytuj) |
| `lista` | `multiseek/report-body-list.html` | numerowana lista opisów |
| `tabela` | `multiseek/report-body-table.html` | + `sumy` z `aggregate()` |
| `pkt_wewn` | jak `tabela` | z punktacją wewnętrzną |
| `pkt_wewn_bez` | jak `tabela` | punktacja sumaryczna |
| `bibtex` | lista opisów | brama dla eksportu `.bib` |
| `pivot` | `multiseek/report-body-pivot.html` | patrz Część II |

`postac=rekordy` zostaje domyślną i **nietkniętą**: dzisiejsza tabela ma ID
rekordu (`pk.0-pk.1`), link „Zobacz", link „Edytuj" do admina konkretnego
podtypu (`_attach_admin_urls`) i klikalny wiersz. To jest wartość redakcyjna tej
strony i jej usunięcie byłoby regresją, której nikt nie zamawiał. Nowe postacie
dokładają się obok, nie zastępują.

Stronicowanie bez zmian (25/stronę). Eksport zawsze na **całym** zbiorze
wyników, nie na widocznej stronie.

### Adaptacja partiali multiseeka (dwie zmiany, obie neutralne)

**A1. Flag `hide_chrome`.** `report-body-list.html` i `report-body-table.html`
renderują przy `export_mode=False` widget ❌ „usuń z wyników"
(`data-remove-result`), który działa **wyłącznie** w multiseeku (sesyjna lista
`MULTISEEK_SESSION_KEY_REMOVED`). Na `/zapytanie/` musi zniknąć. Warunek
zmienia się na `{% if not export_mode and not print_removed and not hide_chrome %}`.

Flag jest **negatywny** celowo: w Django brakująca zmienna jest falsy, więc
pozytywny `{% if allow_remove %}` po cichu wyłączyłby widget także w multiseeku,
który tej zmiennej nie przekazuje. Negatywny flag = zero zmian w zachowaniu
istniejącego konsumenta i zero zmian w `common-results.html`.

**A2. Opcjonalny link edycji.** Partiale nie mają żadnego linku do admina.
Ponieważ na `/zapytanie/` jest on wartością, dokładamy blok
`{% if pokaz_edycje and element.admin_url %}` (znów flag nieprzekazywany przez
multiseek → domyślnie wyłączony). `admin_url` dostarcza istniejące
`ZapytanieView._attach_admin_urls`, wołane teraz dla każdej postaci rekordowej,
nie tylko dla dzisiejszej tabeli.

**Projekcje querysetu.** Render partiali wymaga tych samych `.only()` co
multiseek (`MULTISEEK_RENDER_LIST_FIELDS`, `MULTISEEK_RENDER_TABLE_FIELDS`) —
bez nich `postac=tabela` robi N+1 na `charakter_formalny`/`typ_kbn`, a
`postac=lista` ciągnie całe wiersze `bpp_rekord_mat`. Stałe są już
wyeksportowane z `mymultiseek.py`; strona zapytania je reużywa, dokładając
`pk` (potrzebne dla `js_safe_pk` i `admin_url`).

### Eksport

`GET /zapytanie/eksport/<format>/?model=&query=&postac=&wariant=` →
`ZapytanieExportView(WprowadzanieDanychOrSuperuserMixin, View)`.

| format | dla `model=rekord` | dla `model=autor` |
|---|---|---|
| `csv` | `csv_export_response` (kolumny „dane") | `autor_csv_export_response` |
| `xlsx` | `xlsx_export_response`, `wariant=dane\|opis` | `autor_xlsx_export_response` |
| `html` | `document_export_response` wg `postac` | — (400) |
| `docx` | `document_export_response` wg `postac` | — (400) |
| `bib` | `bibtex_export_response`, **tylko** gdy `postac=bibtex` | — (400) |

Gdy `postac=pivot`, eksport rozgałęzia się **przed** powyższą tabelą: `csv`
i `xlsx` idą do `pivot_csv/xlsx_export_response` (macierz, nie lista rekordów),
a `html`/`docx`/`bib` zwracają 400. Dokładnie ta sama logika co
`MyMultiseekExport.get` (`mymultiseek.py:281`) — tam też pivot jest sprawdzany
jako pierwszy, bo rozmiar wyjścia macierzy nie zależy od liczby rekordów
źródłowych, więc capy rekordowe go nie dotyczą.

Reguła `.bib` tylko przy `postac=bibtex` jest celowo identyczna z
`mymultiseek.py:359` — dwa różne kontrakty na to samo w dwóch miejscach byłyby
pułapką.

Eksport dokumentu przy `postac=rekordy` degraduje do `lista` — redakcyjna
tabela z ID i linkami do admina nie jest postacią raportu do wydruku. Degradacja
(nie błąd 400), bo to najmniej zaskakujące zachowanie dla domyślnej postaci.

Tytuł raportu: `?tytul=` (opcjonalny, przepuszczony przez
`plain_multiseek_report_title`), domyślnie `"Wynik zapytania"`. Strona zapytania
nie ma sesyjnego tytułu jak multiseek i nie zamierzamy go dokładać.

### Limity

| co | limit | dlaczego |
|---|---|---|
| dane (CSV/XLSX) | 25 000 | strona jest za `WprowadzanieDanychOrSuperuserMixin`, nie publiczna jak multiseek (5 000) |
| dokument (HTML/DOCX/`.bib`) | 5 000 | render 25 tys. opisów przez `render_to_string` + sanityzacja + DOCX to minuty CPU i setki MB |
| pivot | `PIVOT_MAX_CELLS=10000`, `PIVOT_MAX_PAIRS=200000` | bez zmian, istniejące bramki |

Przekroczenie → `HttpResponseBadRequest` z komunikatem po polsku podającym
limit i liczbę trafień (jak multiseek). Capy 25 000 / 5 000 **nie dotyczą**
eksportu pivota — tam obowiązują wyłącznie bramki macierzy.

Tytuł raportu z `?tytul=` jest w pełni kontrolowany przez użytkownika i trafia do
nazwy pliku (`Content-Disposition`) oraz do nazwy arkusza XLSX. Idzie więc przez
istniejące `plain_multiseek_report_title` → `_export_filename` /
`_xlsx_worksheet_title` (strip_tags, usunięcie znaków niedozwolonych,
sklejenie do jednej linii, limit 31 znaków dla arkusza). Test musi podać tytuł
z cudzysłowem, znakiem nowej linii i `../` i sprawdzić, że nagłówek odpowiedzi
zostaje jednoliniowy i bez ścieżki.

## Część II — tabela krzyżowa na `/zapytanie/`

Dla `model=rekord` reużywa rejestr `bpp/pivot/rekord.py` bez zmian: 10 wymiarów
(rok, charakter formalny, charakter ogólny, typ MNiSW, koszyk PK, język, źródło,
jednostka, dyscyplina, autor) × 5 metryk (liczba prac, Σ PK, Σ IF, Σ cytowań,
Σ punktacji wewnętrznej). Selektory wymiarów renderują się z
`report-body-pivot.html`, eksport przez `pivot_csv/xlsx_export_response`.

Dla `model=autor` — nowy rejestr, patrz Część III.

## Część III — tabela krzyżowa dla autorów

### Bazy agregacji

Metryka wybiera bazę; baza wyznacza ścieżkę JOIN-u.

| baza | ścieżka ORM | metryki |
|---|---|---|
| **K** kadrowa | sam `bpp_autor` | Liczba autorów = `Count("pk", distinct=True)` |
| **P** prace | `autorzy` → `rekord` (mat. view `bpp_autorzy_mat`) | Liczba prac = `Count("autorzy__rekord_id", distinct=True)` |
| **U** udziały | `cache_punktacja_autora_query` → `rekord` | Σ slotów = `Sum(...__slot)`, Σ pkdaut = `Sum(...__pkdaut)` |

Nazwy odwrotnych relacji zweryfikowane na schemacie: `autorzy` (z
`bpp.models.cache.Autorzy`) i `cache_punktacja_autora_query` (z
`Cache_Punktacja_Autora_Query`, niezarządzany model na tabeli
`bpp_cache_punktacja_autora` — w odróżnieniu od `Cache_Punktacja_Autora` ma
**FK do `Rekord`**, więc widzi `rok`).

Wygenerowany SQL (sprawdzony):

```sql
-- baza U: jednostka × rok, Σ slotów
SELECT bpp_autor.aktualna_jednostka_id, bpp_rekord_mat.rok,
       SUM(bpp_cache_punktacja_autora.slot)
  FROM bpp_autor
  LEFT JOIN bpp_cache_punktacja_autora ON (bpp_autor.id = ...autor_id)
  LEFT JOIN bpp_rekord_mat ON (...rekord_id = bpp_rekord_mat.id)
 GROUP BY 1, 2
```

### Świadome pominięcie: Σ IF / Σ PK / Σ cytowań dla autorów

Te wartości są **rekordowe**. Sumowane per autor zwielokrotniają się między
współautorami: praca pięciu autorów z jednej jednostki wnosi swój IF pięć razy.
Dawanie takiej metryki w UI to produkowanie liczb, które wyglądają wiarygodnie
i są błędne.

Kto chce „Σ IF jednostki", dostaje to **poprawnie** z pivota rekordowego
(wymiar `jednostka`, który idzie przez `autorzy__jednostka_id` i liczy
strategią par — `_pairs_strategy` dedupuje po unikatowych parach
(wymiar, rekord)).

Σ slotów i Σ pkdaut są jedynymi bibliometrycznymi metrykami uczciwie
addytywnymi po autorach — bo z definicji są udziałami. Dzięki temu cały engine
autorski zostaje czystym SQL-em (`COUNT DISTINCT` / `SUM`), bez przebiegu
agregującego w Pythonie.

### Wymiary

**Autorskie** (dostępne w każdej bazie, `expr` jednakowy):

| klucz | etykieta | expr / adnotacja | kolumna? |
|---|---|---|---|
| `jednostka` | Aktualna jednostka | `aktualna_jednostka_id` (fk) | nie |
| `tytul` | Tytuł naukowy | `tytul_id` (fk) | tak |
| `stopien_sluzbowy` | Stopień służbowy | `stopien_sluzbowy_id` (fk) | tak |
| `funkcja` | Aktualna funkcja | `aktualna_funkcja_id` (fk) | tak |
| `plec` | Płeć | `plec_id` (fk) | tak |
| `ma_orcid` | Ma ORCID | adnotacja `Case/When` → bool | tak |
| `orcid_w_pbn` | ORCID w PBN | `orcid_w_pbn` (bool3: TAK/NIE/nieustawione) | tak |
| `ma_pbn_uid` | Ma PBN UID | adnotacja → bool | tak |
| `ma_email` | Ma e-mail | adnotacja → bool | tak |
| `ma_id_kadrowy` | Ma ID kadrowy | adnotacja → bool | tak |
| `rok_urodzenia` | Rok urodzenia | `urodzony__year` | tak |
| `autor` | Autor | `pk` (fk) | nie |

**Publikacyjne** (tylko bazy P/U; `expr` jest słownikiem po bazie):

| klucz | etykieta | baza P | baza U |
|---|---|---|---|
| `rok` | Rok publikacji | `autorzy__rekord__rok` | `cache_punktacja_autora_query__rekord__rok` |
| `dyscyplina` | Dyscyplina pracy | `autorzy__dyscyplina_naukowa_id` | `cache_punktacja_autora_query__dyscyplina_id` |
| `jednostka_pracy` | Jednostka przy pracy | `autorzy__jednostka_id` | `cache_punktacja_autora_query__jednostka_id` |
| `typ_odpowiedzialnosci` | Typ odpowiedzialności | `autorzy__typ_odpowiedzialnosci_id` | — |
| `charakter_formalny` | Charakter formalny pracy | `autorzy__rekord__charakter_formalny_id` | — |

Dwie konsekwencje projektowe:

1. **`expr` jako słownik po bazie.** Ten sam pojęciowy wymiar („rok") ma inną
   ścieżkę ORM w bazie P i U. Wymiary autorskie mają jedną ścieżkę dla
   wszystkich baz (`expr` jako string → normalizowany do słownika przy
   inicjalizacji rejestru). Wymiar niedostępny w danej bazie **nie pojawia się
   w selektorze** — widok podaje partialowi już przefiltrowany słownik wymiarów,
   więc szablon nie musi nic wiedzieć o bazach. Przy nieprawidłowej kombinacji
   przyniesionej z URL-a — cichy fallback do wartości domyślnej (jak dziś
   `parse_pivot_params` robi z `allow_column`).
2. **`PivotDimension.annotation`.** Wymiary „ma ORCID / ma e-mail / ma PBN UID /
   ma ID kadrowy" nie mogą grupować po surowym polu (dostalibyśmy tysiące grup,
   po jednej na wartość). Engine dostaje opcjonalne `annotation` — wyrażenie
   ORM dołożone przez `annotate(**{key: expr})` i grupowanie po aliasie.
   `values("urodzony__year")` kompiluje się natywnie do `EXTRACT(YEAR FROM ...)`
   (sprawdzone), więc rok urodzenia nie potrzebuje adnotacji.

### Semantyka pustych komórek

`LEFT JOIN` w bazach P/U produkuje dla autora bez prac wiersz z `NULL` w
wymiarze publikacyjnym i `NULL`/0 w metryce. Engine **pomija trójki o wartości
zerowej lub `None`** w bazach P/U, żeby macierz nie puchła od autorów bez
dorobku. Wartość `None` w *wymiarze autorskim* (autor bez jednostki) zostaje
i renderuje się jako `— brak —` (stała `BRAK`, zachowanie z pivota rekordowego).

### Presety w pomocy strony

| co chcesz wiedzieć | wiersz × kolumna | metryka |
|---|---|---|
| Struktura kadrowa | jednostka × tytuł | Liczba autorów |
| Audyt kompletności ORCID | jednostka × ma ORCID | Liczba autorów |
| Gotowość do PBN | jednostka × ma PBN UID | Liczba autorów |
| Struktura płci wg tytułów | tytuł × płeć | Liczba autorów |
| Produktywność jednostek | jednostka × rok | Liczba prac |
| Ranking autorów (slotowy) | autor × rok | Σ slotów |
| Udziały dyscyplinowe | dyscyplina × rok | Σ slotów |
| Wkład punktowy jednostek | jednostka × rok | Σ pkdaut |

Presety renderują się jako klikalne linki `?model=autor&postac=pivot&pivot_row=…`
w sekcji pomocy — ten sam wzorzec co istniejące `EXAMPLES` zapytań.

## Część IV — eksport autorów

`postac` dla `model=autor` ogranicza się do `rekordy` (dzisiejsza tabela
autorów) i `pivot` — BibTeX, `lista`, `tabela` i punktacja nie mają sensu bez
opisu bibliograficznego. Formaty eksportu: `csv`, `xlsx`.

Kolumny: nazwisko · imiona · tytuł · stopień służbowy · jednostka · funkcja ·
ORCID · ORCID w PBN · PBN UID · e-mail · ID kadrowy · płeć · **liczba prac** ·
**Σ slotów** · **Σ pkdaut** · ID · URL.

**Metryki dorobku liczone są osobnym zapytaniem agregującym**, nie razem
z wierszem kartoteki. Powód: `Count("autorzy__rekord_id", distinct=True)` idzie
przez `bpp_autorzy_mat`, a `Sum("cache_punktacja_autora_query__slot")` przez
`bpp_cache_punktacja_autora` — dwie różne relacje „do wielu" w jednym
`annotate()` mnożą wiersze przed agregacją i sumy wychodzą zawyżone (klasyczna
pułapka Django „dwa agregaty przez dwa JOIN-y"). Zamiast tego:

1. `Count(distinct)` po `autorzy__rekord_id` — jedno zapytanie `values("pk")
   .annotate(...)`,
2. `Sum(slot)` + `Sum(pkdaut)` po `cache_punktacja_autora_query` — drugie
   zapytanie (te dwa są bezpieczne razem, bo idą **tą samą** relacją),
3. wyniki scalone w słownik `{autor_id: (liczba_prac, slot, pkdaut)}` i doklejane
   do wierszy eksportu.

Test regresyjny musi tworzyć autora z ≥2 pracami i ≥2 wpisami punktacji, żeby
zawyżenie było widoczne, gdyby ktoś kiedyś scalił to w jeden `annotate()`.

XLSX dostaje formatowanie liczbowe na kolumnach metryk, hiperlink na kolumnie
URL (`_apply_xlsx_hyperlinks`), zamrożony nagłówek i auto-szerokości —
reużywając istniejące helpery z `multiseek_export.py`.

## Uprawnienia i bezpieczeństwo

- Wszystkie nowe endpointy pod `WprowadzanieDanychOrSuperuserMixin`
  (`raise_exception = True` → 403, nie redirect). Testy uprawnień dla anonima
  **i** dla `is_staff` poza grupą „wprowadzanie danych" — na eksporcie osobno,
  nie tylko na stronie.
- Brak filtrowania po `ukryte_statusy`: strona jest narzędziem redakcyjnym dla
  zalogowanych z grupy wprowadzania danych, którzy widzą wszystko. Nie
  wprowadzamy multiseekowej gałęzi dla anonima, bo anonim tu nie wchodzi.
- Sanityzacja komórek arkusza (`_sanitize_spreadsheet_cell`, ochrona przed CSV
  injection) obowiązuje też eksport autorów — reużywana, nie pisana od nowa.

## Testy

Nowe pliki:

- `src/bpp/tests/test_pivot_autor.py` — engine autorski: każda z trzech baz,
  wymiary z adnotacją (TAK/NIE), `expr` per baza, dedup (brak zwielokrotnienia
  przy filtrze produkującym JOIN), pominięcie zerowych komórek, bramki
  rozmiaru, etykiety `— brak —`.
- `src/bpp/tests/test_zapytanie_export.py` — 5 formatów × 2 modele:
  content-type, nazwa pliku, nagłówek/pierwszy wiersz, `.bib` tylko przy
  `postac=bibtex`, capy 25 000/5 000, 403 dla anonima i staff-poza-grupą.
- `src/bpp/tests/test_zapytanie_postac.py` — render każdej `postac`, sumy przy
  `tabela`, link edycji tylko dla `is_staff`, **brak** widgetu ❌ na
  `/zapytanie/` (`hide_chrome`) i **obecność** tego widgetu nadal w multiseeku
  (dowód neutralności zmiany A1), degradacja `postac=rekordy` → `lista` przy
  eksporcie dokumentu.

Rozszerzenia:

- `src/bpp/tests/test_playwright/test_multiseek_djangoql.py` — jeden test
  przełączania postaci wyniku i selektorów pivota na `/zapytanie/`.
- Istniejące `test_multiseek_pivot*.py` — **bez zmian**, jako dowód
  neutralności ekstrakcji E3.

Konwencje: pytest bez klas, `@pytest.mark.django_db`, `baker.make`.

## Fazy

| faza | zakres | dowód ukończenia |
|---|---|---|
| **1** | E1 + E2 + `postac` dla rekordów + eksporty CSV/XLSX/HTML/DOCX/.bib | `test_zapytanie_export.py`, `test_zapytanie_postac.py` zielone; multiseekowa suita bez zmian zielona |
| **2** | rekordowy pivot na `/zapytanie/` + eksport pivota | pivot z DjangoQL daje te same liczby co pivot z multiseeka dla równoważnego filtra |
| **3** | E3 (`bpp/pivot/`) + rejestr autorski, baza K + UI | `test_pivot_autor.py` (baza K); 25 testów pivota rekordowego zielone bez zmian w testach |
| **4** | bazy P/U + eksport autorów CSV/XLSX + presety | `test_pivot_autor.py` (P/U), eksport autorów |

Każda faza to jeden commit z newsfragmentem w `src/bpp/newsfragments/`.

## Poza zakresem

- Dyscyplina **zadeklarowana** per rok (`Autor_Dyscyplina`) jako wymiar — wymaga
  parametru roku w UI, inaczej wiersze się zwielokrotnią po latach deklaracji.
  Dziś dostępna jest dyscyplina **pracy**, co pokrywa główne pytania.
- Zapisywane/nazwane konfiguracje pivota (per użytkownik).
- Wykresy z macierzy pivota.
- Eksport pivota do DOCX/HTML (macierz w dokumencie) — CSV/XLSX wystarcza.
