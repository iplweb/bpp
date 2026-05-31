# Seed domyślnych definicji raportów (slice A tematu „konfigurowalne raporty")

Data: 2026-05-31
Status: do recenzji użytkownika
Branch/worktree: `feat/nowe-raporty-seed-domyslnych` / `~/Programowanie/bpp-seed-raportow`

## Problem

Na gołym serwerze nie ma definicji raportów (`flexible_reports.Report`), więc
strony raportów pokazują komunikat „nieskonfigurowany" (temat 1). Brak
mechanizmu, który zakłada **domyślne, działające** definicje 4 raportów
(autor / jednostka / wydział / uczelnia). Istniejący fixture
`src/nowe_raporty/fixtures/0001_initial_data.json` jest **zepsuty** (odwołuje się
do `ContentType` po PK → `ForeignKeyViolation` na świeżej bazie) i **niekompletny**
(brak `raport-uczelni`), i nikt go automatycznie nie ładuje.

## Cel

Idempotentny, nienadpisujący seed domyślnych 4 raportów: uruchamialny ręcznie
komendą **oraz** automatycznie po `migrate`. Źródłem są dane dostarczone przez
użytkownika (dump `dumpdata flexible_reports --natural-foreign`, plik
`~/raporty_default.json`), potraktowane jako baza do **uporządkowania i
uzupełnienia**, nie do wiernego importu.

## Decyzje (zatwierdzone w brainstormingu)

1. **Trigger:** management command `seed_raporty` (ręcznie) + idempotentny
   `post_migrate` (automat na świeżym deployu).
2. **Nie nadpisuje** istniejących danych — twardy wymóg.
3. **Jedna wspólna `Table`** dla wszystkich raportów (jak w danych usera) —
   zostawiamy. (Osobny feature „klonuj tabelę" zaparkowany na później.)
4. **Poziom czyszczenia:** poprawiamy oczywiste usterki (zbite tagi HTML w
   szablonach, błędne labele `2.1` „rozdziału") + dorabiamy `raport-uczelni`,
   bez zmian w logice DSL/datasource.

## Architektura danych (z dumpu usera)

- 1 `Table` („Publikacje autorów", base_model `bpp.rekord`) + 7 `Column`
  (Lp, Opis bibliograficzny, IF, Pkt. MNiSW, Typ KBN, Rok, ID) + 2 `ColumnOrder`
  (Rok malejąco, Opis rosnąco).
- 18 `Datasource` (DSL na `bpp.rekord`). Sekcje `1.x`, `3`, `4.x` — wspólne,
  **bez** filtra po obiekcie (scoping z `set_base_queryset` w kodzie). Sekcje
  `2.x` — warianty per typ obiektu z jawnym `autor=/jednostka=/wydzial= {{ obiekt.pk }}`
  (konieczne: pinują typ odpowiedzialności do konkretnego autora na jednym
  wierszu autorstwa — „przefiltrowana lista" tego nie wyraża).
- 3 `Report` (jednostek/autorów/wydziałów), każdy 12 sekcji
  (`1.1–1.5`, `2.1–2.3`, `3`, `4.1–4.3`), `4.3 Inne` = catch-all
  (`data_from=DATA_FROM_EXCEPT_CATCHALL`).

## Rozwiązanie

Decyzja: definicje i logika seedowania **w kodzie Pythona**, nie w pliku
JSON/fixture. Uzasadnienie: `loaddata` i tak odrzucone (nadpisuje po PK), więc
loader piszemy ręcznie niezależnie — wtedy JSON + custom loader to dwa artefakty
+ glue na PK + nieczytelny review, a Python budujący obiekty wprost to jeden
artefakt, zero PK, czytelny diff, komentarze przy DSL. Dodatkowo Python pozwala
wyrazić symetrię autor/jednostka/wydział/uczelnia (generowanie wariantów `2.x`
z jednego wzorca) i zdeduplikować prawie-identyczny szablon HTML.

### 1. Definicje domyślne (źródło prawdy) — Python

`src/nowe_raporty/seeding/definicje.py` — czytelne stałe + funkcje budujące,
treść DSL/kolumn/szablonu przepisana z dumpu usera **z poprawkami**:

- **Kolumny** wspólnej tabeli: jedna lista definicji (Lp, Opis bibliograficzny,
  IF, Pkt. MNiSW, Typ KBN, Rok, ID) + kolejność (Rok malejąco, Opis rosnąco).
- **Datasource'y** jako buildery:
  - `1.x`, `3`, `4.x` — wspólne, bez filtra po obiekcie (jeden zestaw).
  - `2.x` — **generowane z jednego wzorca** parametryzowanego nazwą pola
    obiektu: `autor` / `jednostka` / `wydzial` / `None`. Dla `None` (uczelnia)
    klauzula `… = {{ obiekt.pk }}` znika → agregacja po całej uczelni. To
    eliminuje duplikację osobnych prawie-identycznych datasource'ów z dumpu.
  - **`raport-uczelni` 2.x** (wzorzec z `field=None`) — **do sanity-checku przez
    usera**: semantyka monografii/rozdziału/redakcji na poziomie uczelni to mój
    wybór projektowy.
- **Szablon HTML** raportu — jedna funkcja parametryzowana nagłówkiem („Raport
  autora/jednostki/wydziału/uczelni"), z **poprawionymi** tagami (`<h2>…</h3>`
  → spójne `h2`/`h3`; `4.1/4.2/4.3` jako `<h3>` pod „4. Inne"). Zastępuje 4×
  prawie-identyczny szablon z dumpu.
- **Labele** `2.1` poprawione: „Autorstwo **monografii**" (nie „rozdziału").
- **Definicje 4 raportów**: slug + tytuł + lista sekcji (które datasource'y,
  w jakiej kolejności), w tym dorobiony `raport-uczelni`.

### 2. Loader — `seed_default_reports()` + management command

`src/nowe_raporty/seeding/__init__.py` (funkcja `seed_default_reports()`),
wołana przez `src/nowe_raporty/management/commands/seed_raporty.py`.
Idempotentna aplikacja, **bez `loaddata`**:

1. **`Table`/`Datasource`**: `get_or_create` po `label` (jedyny ludzko-stabilny
   klucz; `flexible_reports` nie ma slug-a na tych modelach, a pól dodać nie
   można — to obcy pakiet). Istnieje po label → używam, **nie dotykam**.
   **`Column`/`ColumnOrder`** tworzone **atomowo razem z `Table`** w gałęzi
   „zakładam tabelę"; gdy `Table` istnieje po label — kolumn/`ColumnOrder`-ów
   **nie tykamy**.
2. **`Report`**: `get_or_create` po `slug`. Istnieje → **pomijam w całości**
   (z elementami). Brak → tworzę `Report` + `ReportElement`-y wskazujące na
   współdzieloną tabelę i odpowiednie datasource'y.
3. **`ContentType`** (base_model): `ContentType.objects.get_by_natural_key(...)`.
4. Nigdy żadnego `UPDATE`/`delete`. Podsumowanie (utworzone vs pominięte) na
   stdout.

Flaga `--force`? **Nie** — sprzeczne z „nie nadpisuj". Re-seed uzupełnia tylko
brakujące.

### 3. Auto-seed na `post_migrate`

W `src/nowe_raporty/apps.py` (gdzie już jest `create_entries` na `post_migrate`):
dołożyć handler `seed_default_reports` połączony tym samym wzorcem, **za tym
samym guardem** `if settings.TESTING: return`. Handler woła funkcję seedującą z
komendy (wspólna logika w jednym miejscu, np. `nowe_raporty/seeding.py`).
Pod testami auto-seed się NIE odpala → testy zakładające brak raportu (m.in.
temat 1) zostają deterministyczne; komenda działa zawsze (jawnie).

## Idempotencja i „nie nadpisuj" — przypadki brzegowe

- Pusta baza → tworzy wspólną tabelę + datasource'y + 4 raporty.
- Część raportów istnieje (np. tylko `raport-autorow`) → tworzy brakujące
  (w tym `raport-uczelni`), reużywa wspólnej tabeli/datasource'ów po label.
- Redaktor wyedytował raport/tabelę → seed go **nie tyka** (skip po slug/label).
- Ryzyko świadome: jeśli redaktor **zmieni `label`** wspólnej tabeli/datasource,
  re-seed nie rozpozna jej i może utworzyć duplikat. Akceptowalne dla defaultów;
  udokumentowane.

## Testy (TDD, pytest, testcontainers)

W `src/nowe_raporty/tests/test_seed_raporty.py`:

1. **Pusta baza → komplet.** `call_command("seed_raporty")` tworzy 4 raporty
   (sluga `raport-autorow/-jednostek/-wydzialow/-uczelni`), 1 wspólną `Table`,
   komplet kolumn; raporty renderowalne.
2. **Idempotencja.** Dwukrotne wywołanie → liczby `Report`/`Table`/`Datasource`/
   `Column` bez zmian (brak duplikatów).
3. **Nie nadpisuje raportu.** Pre-create `Report(slug="raport-autorow")` z
   sentinel `title`/`template`; po seedzie ten raport **niezmieniony**, pozostałe
   3 utworzone.
4. **Nie nadpisuje tabeli.** Pre-create `Table(label="Publikacje autorów")` z 1
   kolumną; po seedzie tabela nietknięta (nadal 1 kolumna), raporty na nią
   wskazują.
5. **Integracja z tematem 1.** Po seedzie wejście na `*_generuj` dla istniejącego
   obiektu zwraca 200 i renderuje raport (a nie komunikat „nieskonfigurowany").
6. **`raport-uczelni` realnie działa.** Seed + wejście na `uczelnia_generuj` →
   200 (sanity całej dorobionej definicji).

Auto-seed (`post_migrate`) jest pod `settings.TESTING` wyłączony, więc testy
wołają komendę/funkcję jawnie i kontrolują stan.

## Pliki

- nowy: `src/nowe_raporty/seeding/__init__.py` (funkcja `seed_default_reports()`
  + logika idempotentna)
- nowy: `src/nowe_raporty/seeding/definicje.py` (stałe + buildery: kolumny,
  datasource'y, szablon, definicje 4 raportów)
- nowy: `src/nowe_raporty/management/__init__.py`,
  `src/nowe_raporty/management/commands/__init__.py` (jeśli brak)
- nowy: `src/nowe_raporty/management/commands/seed_raporty.py`
- modyfikacja: `src/nowe_raporty/apps.py` (drugi handler `post_migrate` za
  guardem `settings.TESTING`)
- nowy: `src/nowe_raporty/tests/test_seed_raporty.py`
- usunięty: `src/nowe_raporty/fixtures/0001_initial_data.json` — martwy ślad po
  Django <1.9 auto-loadowanym `initial_data` (od 2015 nieładowany niczym),
  zepsuty (ContentType po PK). Zastąpiony tym seedem.

Bez plików JSON/fixture z danymi — definicje żyją w `seeding/definicje.py`.

## Poza zakresem

- Konfigurowalność listy raportów / data-driven menu (slice B).
- Per-uczelnia multi-tenant uprawnienia (slice C).
- Feature „klonuj tabelę" (zaparkowany).
- Bug 500 w eksporcie przy braku `Report` (z tematu 1) — domykany przy slice B.
- Przeprojektowanie datasource'ów pod „karm przefiltrowaną listą".
