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

### 1. Plik danych (źródło prawdy)

`src/nowe_raporty/data/domyslne_raporty.json` — format serializacji Django
(lista `{model, pk, fields}`, jak `dumpdata --natural-foreign`), wyprodukowany z
dumpu usera z poprawkami:

- **dodany `raport-uczelni`** (slug `raport-uczelni`, title „Raport uczelni"):
  ta sama struktura 12 sekcji; `1.x/3/4.x` współdzielą istniejące datasource'y
  bez filtra; `2.x` → **3 nowe** datasource'y „… - uczelnia" = warunki
  monografii/rozdziału/redakcji **bez** `…= {{ obiekt.pk }}` (agregacja po całej
  uczelni; base_queryset = `Rekord.all()`/`afiliuje`). **Do sanity-checku przez
  usera** — semantyka DSL dla uczelni to mój wybór.
- **poprawione szablony** wszystkich raportów: `<h2>…</h3>` → spójne `h2`/`h3`,
  sekcje `4.1/4.2/4.3` jako `<h3>` pod „4. Inne".
- **poprawione labele** datasource'ów `2.1` jednostka/wydział: „Autorstwo
  **monografii**" zamiast „Autorstwo **rozdziału** monografii".

Format `dumpdata` zachowany celowo: user może odświeżyć plik wklejając nowy
`dumpdata --natural-foreign`, a loader (niżej) i tak nadaje sens PK-om lokalnie.

### 2. Loader — management command `seed_raporty`

`src/nowe_raporty/management/commands/seed_raporty.py`. NIE używa `loaddata`
(bo `loaddata` robi INSERT-or-UPDATE po PK → nadpisałoby/kolidowało). Zamiast
tego własna, idempotentna aplikacja:

1. Wczytuje JSON, buduje mapę `pk-w-pliku → obiekt-w-bazie` w pamięci.
2. **`Table`/`Datasource`**: `get_or_create` po `label` (jedyny ludzko-stabilny
   klucz; `flexible_reports` nie ma slug-a na tych modelach, a pól dodać nie
   można — to obcy pakiet). Istnieje po label → używam, **nie dotykam**.
   **`Column`/`ColumnOrder`** nie mają własnego klucza — tworzone są **atomowo
   razem z `Table`** w gałęzi „zakładam tabelę"; gdy `Table` istnieje po label,
   jej kolumn ani `ColumnOrder`-ów **nie tykamy** w ogóle.
3. **`Report`**: `get_or_create` po `slug`. Istnieje → **pomijam w całości**
   (z elementami). Brak → tworzę `Report` + jego `ReportElement`-y wskazujące na
   (współdzieloną) tabelę i odpowiednie datasource'y.
4. **`ContentType`** (base_model): rozwiązywany przez
   `ContentType.objects.get_by_natural_key(app_label, model)`.
5. Nigdy żadnego `UPDATE`/`delete`. Na końcu wypisuje podsumowanie
   (utworzone vs pominięte) na stdout.

Flaga `--force`? **Nie** — sprzeczne z „nie nadpisuj". Re-seed = uzupełnia tylko
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

- nowy: `src/nowe_raporty/data/domyslne_raporty.json`
- nowy: `src/nowe_raporty/seeding.py` (funkcja `seed_default_reports()`)
- nowy: `src/nowe_raporty/management/commands/seed_raporty.py`
- nowy: `src/nowe_raporty/management/__init__.py`,
  `src/nowe_raporty/management/commands/__init__.py` (jeśli brak)
- modyfikacja: `src/nowe_raporty/apps.py` (drugi handler `post_migrate`)
- nowy: `src/nowe_raporty/tests/test_seed_raporty.py`
- (rozważyć) usunięcie/zastąpienie zepsutego
  `src/nowe_raporty/fixtures/0001_initial_data.json` — osobno, nie blokuje.

## Poza zakresem

- Konfigurowalność listy raportów / data-driven menu (slice B).
- Per-uczelnia multi-tenant uprawnienia (slice C).
- Feature „klonuj tabelę" (zaparkowany).
- Bug 500 w eksporcie przy braku `Report` (z tematu 1) — domykany przy slice B.
- Przeprojektowanie datasource'ów pod „karm przefiltrowaną listą".
