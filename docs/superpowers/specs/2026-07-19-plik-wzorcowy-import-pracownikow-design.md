# Plik wzorcowy importu pracowników — rozdzielenie od fixture'a testowego

Data: 2026-07-19
Obszar: `src/import_pracownikow/`

## Problem

Przycisk „pobierz plik wzorcowy" na `/import_pracownikow/new/` serwuje
`src/import_pracownikow/static/import_pracownikow/import_pracownikow_przyklad.xlsx`,
który jest **symlinkiem** do `../../tests/testdata.xlsx` — czyli do fixture'a
testowego, do którego odwołuje się 14 miejsc w 6 plikach testów. Skutki:

1. **Niekompletna ramka.** Nagłówek jest w wierszu 7, dane w wierszu 8;
   obramowanie mają wszystkie kolumny oprócz M i N (`PBN UUID`, `BPP ID`) —
   ślad po ręcznym dołożeniu kolumn do gotowej tabelki. Kolumna O (`Wymiar
   etatu`) tuż obok ma znów pełną ramkę.
2. **Materiał surowy, nie dla klienta.** Jeden wiersz „Kowalski Jan", opisy
   wrzucone luzem w wierszach 2–5, literówka „dancyh" w wierszu 5.
3. **Sprzężenie dwukierunkowe.** Upiększenie pliku dla klienta dotyka danych
   testowych; zmiana potrzeb testów zmienia to, co pobiera klient.

`import_pracownikow` jest **jedynym** importem z takim symlinkiem —
`import_dyscyplin` i `import_list_if` mają prawdziwe, dedykowane pliki.

Weryfikacja empiryczna (prawdziwy kod mapowania puszczony na plik):
auto-rozpoznanie kolumn działa **bezbłędnie** — nagłówek znajduje się w
wierszu 7, wszystkie 15 kolumn trafia na właściwe pola docelowe, walidacja
przechodzi. Dwa nagłówki działają tylko dzięki krzepkości normalizatora:
`Data końca zatrudnienia ` (końcowa spacja) ratuje `.strip()`, a
`Podstawowe miejsce pracy \nTAK/NIE` (znak nowej linii) — `.split("\n")[0]`.
To krucha zależność, na której nie chcemy polegać w materiale dla klienta.

## Decyzje (ustalone w brainstormingu)

- **Rozdzielić:** osobny, dedykowany plik wzorcowy; `testdata.xlsx` zostaje
  nietknięty jako fixture.
- **Zakres kolumn:** te same 15 kolumn co dziś — zmienia się forma, nie
  zakres. Zestaw jest sprawdzony w boju u klientów.
- **Zawartość:** nagłówek w wierszu 1 + kilka wierszy przykładowych; opisy
  (Numer / BPP ID / PBN UUID) w komentarzach komórek + zakładka „Opis kolumn".
- **Utrzymanie:** generator w repo (źródło prawdy) + wygenerowana binarka +
  test kontraktowy.

## Architektura

Trzy artefakty, zero migracji, zero dotykania danych testowych.

| Artefakt | Rola |
|---|---|
| `management/commands/generuj_plik_wzorcowy.py` | Generator — komenda Django budująca XLSX przez openpyxl. Źródło prawdy dla treści i formatowania. |
| `static/import_pracownikow/import_pracownikow_przyklad.xlsx` | Wygenerowana binarka — **przestaje być symlinkiem**, staje się prawdziwym plikiem (produktem generatora), zacommitowanym. |
| `tests/test_plik_wzorcowy.py` | Test kontraktowy — ładuje binarkę i przepuszcza przez prawdziwy kod mapowania. |

Generator ląduje w `management/commands/`, nie w `eksport.py` — `eksport.py`
służy do eksportu wyników importu (inna odpowiedzialność). Komenda
zarządzająca to naturalne miejsce na „zbuduj artefakt do repo", regenerowalne
jednym `uv run python src/manage.py generuj_plik_wzorcowy`.

Usunięcie symlinku rozcina przyczynę źródłową: `testdata.xlsx` (14 odwołań w
6 plikach testów) dalej działa, a plik wzorcowy przestaje być z nim sprzężony.

## Zawartość i formatowanie pliku

**Układ:** nagłówek w wierszu 1 (bold, pełna ramka `LRTB` na wszystkich 15
kolumnach), wiersze przykładowe od wiersza 2. Wzorowane na
`import_dyscyplin/default.xlsx`.

**15 kolumn** (bez zmian zakresu, dokładnie te co dziś):
`Numer · Nazwisko · Imię · ORCID · Tytuł/Stopień · Stanowisko ·
Grupa pracownicza · Nazwa jednostki · Wydział · Data zatrudnienia ·
Data końca zatrudnienia · Podstawowe miejsce pracy · PBN UUID · BPP ID ·
Wymiar etatu`

**Czyszczenie śmieci formatujących w nagłówkach** (brzmienie bez zmian —
mapują się poprawnie):

- usunąć końcową spację z „Data końca zatrudnienia";
- usunąć znak nowej linii z „Podstawowe miejsce pracy \nTAK/NIE"; podpowiedź
  „TAK/NIE" przenieść do komentarza komórki (dziś działała tylko dzięki
  `.split("\n")[0]` w normalizatorze — krucha zależność).

**4 wiersze przykładowe** pokrywające różne przypadki:

| przypadek | co pokazuje |
|---|---|
| pełny etat, zatrudnienie trwa | komplet pól, `data końca` pusta, „Pełny etat" |
| część etatu | `1/2` / „Połowa etatu", inna grupa pracownicza |
| zatrudnienie zakończone | wypełniona `data końca zatrudnienia` |
| minimum danych | tylko wymagane pola + brak ORCID/PBN/BPP ID (pokazuje opcjonalność) |

Dane fikcyjne w konwencji repo („Kowalski Jan", „testowa" jednostka), żadnych
realnych danych osobowych. `import_pracownikow` nie ma kolumny PESEL, więc
problem PESEL nie występuje.

**Objaśnienia** `Numer` / `BPP ID` / `PBN UUID` (dziś w luźnym bloczku z
literówką „dancyh"): w komentarzach komórek nagłówka + osobna zakładka
**„Opis kolumn"** (druga karta arkusza: kolumna → znaczenie → wymagana/
opcjonalna).

**Reguła „jeden arkusz z danymi" — krytyczne ograniczenie układu zakładki.**
`liczba_arkuszy_z_danymi()` (`import_common/util.py:243`) liczy arkusze z
**rozpoznanym nagłówkiem**, tj. arkusze, w których fuzzy-detekcja
(`find_similar_row`) znajdzie wiersz z ≥ `MIN_POINTS` (=2) znanymi nazwami
kolumn. Gdyby zakładka „Opis kolumn" miała gdziekolwiek wiersz zawierający ≥2
nazwy kolumn obok siebie (np. poziomą listę nazw), zostałaby policzona jako
DRUGI arkusz danych → `sprawdz_pojedynczy_arkusz` podniósłby
`BadNoOfSheetsException` i plik wzorcowy NIE dałby się zaimportować.

Dlatego zakładka „Opis kolumn" MUSI mieć układ **pionowy**: nazwy kolumn jedna
pod drugą w kolumnie A (po jednej na wiersz), obok proza opisowa. Wtedy żaden
pojedynczy wiersz nie zawiera ≥2 znanych nazw → detektor nagłówka go nie łapie
→ arkusz nie liczy się jako drugi arkusz danych. Nagłówek samej zakładki
(„Kolumna" / „Znaczenie" / „Wymagana") również nie jest zbiorem synonimów, więc
też nie trafia. To ograniczenie jest **egzekwowane testem** (patrz niżej: test
asertuje `liczba_arkuszy_z_danymi() == 1`).

## Test kontraktowy

`test_plik_wzorcowy.py` ładuje **realną binarkę z dysku** (nie regeneruje w
locie; testujemy to, co klient faktycznie pobiera) i asertuje kontrakt
sprawdzony dziś ręcznie:

1. nagłówek znajduje się fuzzy-detekcją z parametrami importu
   (`find_similar_row_in_rows(rows, try_names=TRY_NAMES, min_points=MIN_POINTS)`
   nie zwraca `None`);
2. **każda** kolumna mapuje się na pole docelowe — `POLE_POMIN` nie występuje
   w wartościach `zaproponuj_mapowanie(...)`;
3. walidacja przechodzi — `waliduj_mapowanie(...) == []`;
4. **plik ma dokładnie jeden arkusz z danymi** —
   `zrodlo.liczba_arkuszy_z_danymi() == 1` (asercja mocniejsza niż „nie
   podnosi wyjątku": pilnuje wprost, że zakładka „Opis kolumn" nigdy nie
   przybrała kształtu danych i nie wpadła w fuzzy-detekcję nagłówka).

Dodatkowe tanie asercje:

- nagłówek nie zawiera `\n` ani końcowej spacji (czyszczenie śmieci nie
  wróciło);
- plik nie jest symlinkiem (`not os.path.islink(...)` — rozdzielenie się
  utrzymało).

To jest sedno zabezpieczenia przed gniciem: jeśli ktoś przemianuje synonim w
`mapping.py` albo kolumnę w generatorze, punkt 2 lub 3 się wywali i CI to
złapie.

## Obsługa błędów

Generator jest deterministyczny i offline (żadnego ORM, sieci, wejścia
użytkownika). Jedyny realny błąd to problem z zapisem pliku — openpyxl/OS
zgłoszą wyjątkiem, który propaguje (komenda zarządzająca; traceback na konsoli
to właściwe zachowanie, zero `except: pass`). Nadpisanie istniejącego pliku
jest zamierzone (regeneracja).

## Newsfragment

`src/bpp/newsfragments/import_pracownikow.bugfix.rst`:

> Poprawiono plik wzorcowy importu pracowników (kompletna ramka, przykładowe
> wiersze, opis kolumn); rozdzielono go od danych testowych.

## Poza zakresem (YAGNI)

- Rozszerzanie o pola opcjonalne (drugie imię, stopień służbowy, stanowisko
  dydaktyczne, e-mail) — świadomie NIE; zestaw 15 kolumn zostaje.
- Generacja pliku w locie z widoku — odrzucona; plik statyczny.
- Refaktor `testdata.xlsx` ani odwołań testowych do niego.
