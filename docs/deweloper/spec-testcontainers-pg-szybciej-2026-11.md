# Spec: szybszy PostgreSQL w kontenerach testowych (listopad 2026)

Przegląd konfiguracji serwera PostgreSQL startowanego przez
`pytest-testcontainers-django` (sekcja `[tool.pytest-testcontainers-django]`
w `pyproject.toml`, obraz `iplweb/bpp_dbserver:psql-16.13`). Przegląd
zrobiony 2026-11-08 **bez uruchamiania** czegokolwiek — tylko czytanie
konfiguracji, kodu pluginu (`.venv/.../pytest_testcontainers_django/`) i
skryptów obrazu (`iplweb/bpp-dbserver`: `docker-entrypoint-autotune.sh`,
`autotune.sh`). Liczby wpływu to szacunki — weryfikuje je Faza 0/5.

## Skąd jest obraz

`iplweb/bpp_dbserver:psql-16.13` pochodzi z Docker Huba i jest
**zamrożony**: ostatni build 2026-04-27 z commita `b351895e` repo
`iplweb/bpp-dbserver`. Od 2026-06-13 (`345950b1`, #8) to repo **nie
buduje już obrazu**. Zawiera tylko `autotune.sh` +
`docker-entrypoint-autotune.sh` do podmontowania na stockowy `postgres`,
a CI robi wyłącznie smoke test na `postgres:16/17/18`. Nikt więc nie
odświeża obrazu (poprawki bezpieczeństwa Debiana, nowe minor PG), a
zmiany w repo **nie trafiają** do testów BPP.

Zawartość zamrożonego obrazu (Dockerfile z `b351895e`, sprawdzone
`docker run --entrypoint cat`):

- `FROM postgres:16.13` + `postgresql-plpython3-16` + locale `pl_PL`,
- `ENV POSTGRES_INITDB_ARGS="--locale-provider=icu --icu-locale=pl-PL"`,
- `ENV POSTGRES_HOST_AUTH_METHOD=trust`,
- stara wersja autotune w Pythonie (`/autotune.py`), z tymi samymi
  regułami co obecny `autotune.sh`.

Repo `iplweb/bpp-dbserver` jest **zarchiwizowane** (GitHub
`archived: true`). Obraz na Docker Hubie zostaje, ale już nie powstanie
nowy.

Gdzie potrzebny jest `plpython3u`:

- **Testy na załadowanym baseline: nie.** Baza testowa ma języki
  `internal, c, sql, plpgsql` i rozszerzenia `btree_gist, hstore, pg_trgm,
  unaccent`, a suita przechodzi (Faza 0). `plpython3u` usunęła migracja
  `0442`, a kolację libc `pl_PL` migracja `0443`.
- **Budowa baseline od zera (`make rebuild-baseline`): tak.** Migracje
  `0001…0439` tworzą funkcje `LANGUAGE plpython3u`, a starych migracji
  nie wolno edytować. `PG_BASELINE["REBUILD_IMAGE"]` musi więc zostać
  `iplweb/bpp_dbserver:psql-16.13`. Ten zamrożony obraz staje się
  narzędziem archiwalnym tylko do budowania baseline.

## Stan obecny

`postgres_env = { POSTGRESQL_UNSAFE_BUT_FAST = "1",
POSTGRESQL_MAX_LOCKS_PER_TRANSACTION = "512" }`. Autotune obrazu dopisuje
wtedy do `/postgresql_optimized.conf` (dołączanego przez `include_if_exists`
na końcu `postgresql.conf`):

- `fsync=off`, `full_page_writes=off`, `synchronous_commit=off`,
  `wal_level=minimal`, `max_wal_senders=0`, `archive_mode=off`,
  `wal_writer_delay=10s`, `commit_delay=100000`, `random_page_cost=1.1`,
  `effective_io_concurrency=200`,
- rozmiary pamięci liczone pgtune-owo z wykrytego RAM-u,
- `max_parallel_workers_per_gather` = 4 (przy ≥7 CPU).

Główne przełączniki „unsafe" są więc na miejscu. Problemy:

| # | Problem | Skutek |
|---|---------|--------|
| P1 | Wrapper obrazu woła `docker-ensure-initdb.sh` **bez argumentów**, a `include` z trybem unsafe dopisuje dopiero **po** nim. `initdb` + import `baseline.sql` (1,5 MB, tysiące autocommitów psql) idą z `fsync=on`, `synchronous_commit=on`, `shared_buffers=128MB`. | Wolniejszy zimny start każdego świeżego kontenera. |
| P2 | Autotune czyta `/sys/fs/cgroup/memory.max` kontenera; testcontainers nie ustawia limitu → `max` → fallback na `/proc/meminfo` hosta (37,6 GB). Wychodzi `shared_buffers≈8,9GB`, `maintenance_work_mem=2GB`, `effective_cache_size≈27GB` dla bazy rzędu kilkudziesięciu MB. | Każdy commit z `TRUNCATE`/`DROP` (teardown `TransactionTestCase`, `DROP DATABASE`) skanuje wszystkie ~1,1 mln nagłówków buforów (poza recovery PG nie ma szybkiej ścieżki); niepotrzebna presja na `docker-limited.slice`. |
| P3 | `jit` = domyślnie `on` (PG16). Ciężkie widoki BPP (UNION-y) potrafią przebić `jit_above_cost`. | Kompilacja LLVM: dziesiątki–setki ms na zapytanie, zero zysku przy małych danych. |
| P4 | `autovacuum` = `on` na kilkunastu bazach testowych (po jednej na worker xdist) z ciągłym insert/truncate. | Tło zjada CPU, które przy `-n auto` jest i tak wysycone. |
| P5 | `max_parallel_workers_per_gather=4`. | Na małych danych równoległość to koszt startu workerów + walka o CPU z xdist; ryzyko przepełnienia domyślnego `/dev/shm` (64 MB). |
| ~~P6~~ | ~~Uwierzytelnianie SCRAM przy `CONN_MAX_AGE=0`.~~ **Nieaktualne**: obraz ma już `POSTGRES_HOST_AUTH_METHOD=trust`. | — |
| P7 | PGDATA na overlayfs (CI w `docker-compose.test.yml` ma tmpfs). Plugin nie ma opcji `tmpfs`/`shm_size`/`command`. | Umiarkowany — przy `fsync=off` zapisy i tak idą async przez page cache. |

Nieistotne / świadomie pomijane:

- `commit_delay=100000` (100 ms!) wygląda groźnie, ale `XLogFlush` pomija
  go, gdy `fsync=off` (`enableFsync=false`) — no-op.
- Redis (`redis:7-alpine`) robi domyślne snapshoty RDB (fork w trakcie
  testów) — osobny temat, plugin i tak nie pozwala przekazać `command`.
- ICU `pl-PL` w testach **jest**: zapewnia go `ENV POSTGRES_INITDB_ARGS`
  w obrazie. Pułapka: ustawienie `POSTGRES_INITDB_ARGS` w `postgres_env`
  **nadpisuje** wartość z obrazu, więc trzeba powtórzyć argumenty ICU
  (patrz Faza 2).

## Plan — kolejność prac

Zasada: najpierw zmiany wyłącznie w repo `bpp` (zero zależności od wydań
obrazu/pluginu), każda faza mierzalna osobno, potem poprawki u źródła.

### Faza 0 — pomiar bazowy (przed jakąkolwiek zmianą)

Po zakończeniu weryfikacji prędkości maszyny. Na laptopie tylko wycinki
(pełna suita na CI / serwerze domowym), za każdym razem **bez**
`PYTEST_TESTCONTAINERS_REUSE` (init skrypty lecą tylko na świeżym
kontenerze):

1. **Zimny start**: czas jednego trywialnego testu z `django_db`
   (`time uv run pytest <jeden test> -p no:randomly`) — 3 powtórzenia,
   mediana.
2. **Ścieżka TRUNCATE**: wybrany moduł z dużą liczbą testów
   `transactional_db` / `live_server`, `--durations=20`.
3. **Ścieżka zapytań**: moduł z ciężkimi widokami (raporty / `rekord`),
   `--durations=20`.
4. Zrzut faktycznej konfiguracji z kontenera (do porównania po zmianach):
   ```sql
   SELECT name, setting, unit, source FROM pg_settings
   WHERE name IN ('fsync','synchronous_commit','full_page_writes',
     'shared_buffers','maintenance_work_mem','effective_cache_size',
     'work_mem','max_connections','jit','autovacuum',
     'max_parallel_workers_per_gather');
   ```

Wyniki wpisać do tabeli na końcu tego dokumentu.

### Fazy 1–2 — `docker/test-db/test-fast.sql` (P1–P5) — WDROŻONE

Pierwotny plan zakładał Fazę 1 przez zmienną autotune
(`POSTGRESQL_RAM_THIS_MUCH_GB`, mimo nazwy w MB) i Fazę 2 przez skrypt
SQL z kilkoma ustawieniami. W implementacji obie fazy połączyliśmy w
**jeden plik jako jedyne źródło prawdy**. Plik ustawia przez `ALTER SYSTEM`
cały tuning testowy, czyli także pamięć, WAL i locki. Dzięki temu:

- nie zależymy od autotune zamrożonego obrazu ani od jego mylącej
  zmiennej; `postgres_env` nie ustawia już `POSTGRESQL_*`,
- ten sam plik działa bez zmian na stockowym obrazie `postgres` (Faza 6).

```toml
postgres_init_scripts = [
    "docker/test-db/test-fast.sql",
    "baseline-sql/baseline.sql",
]
postgres_env = { POSTGRES_INITDB_ARGS = "--locale-provider=icu --icu-locale=pl-PL --no-sync" }
```

Plugin nadaje plikom prefiksy `00-` i `01-` według kolejności na liście
(stąd nazwa pliku bez prefiksu), więc skrypt wykona się przed importem
baseline. Ustawienia (pełna lista i uzasadnienie są w komentarzach pliku):
`fsync`, `synchronous_commit`, `full_page_writes` = `off` (sighup, czyli
od razu, także dla importu baseline); `wal_level=minimal`,
`max_wal_senders=0`, `archive_mode=off`, `max_wal_size=4GB`,
`checkpoint_timeout=30min`; `shared_buffers=1GB`,
`effective_cache_size=3GB`, `maintenance_work_mem=256MB`, `work_mem=8MB`;
`max_connections=250`, `max_locks_per_transaction=512`; `jit=off`,
`max_parallel_workers_per_gather=0`, `random_page_cost=1.1`,
`autovacuum=off`.

Dlaczego to działa:

- `docker_process_init_files` puszcza `.sql` przez `psql -f` w trybie
  autocommit, więc `ALTER SYSTEM` (niedozwolone w bloku transakcji)
  przechodzi. Użytkownik `bpp` jest superuserem w oficjalnym entrypoincie.
- Zapis trafia do `$PGDATA/postgresql.auto.conf`, który PG czyta **po**
  `postgresql.conf`, łącznie z `include_if_exists` autotune. Te wartości
  wygrywają więc z autotune, a parametry `postmaster` wchodzą przy
  restarcie z serwera tymczasowego na docelowy.
- `POSTGRES_INITDB_ARGS` **nadpisuje** `ENV` z obrazu, dlatego powtarza
  argumenty ICU. `--no-sync`: initdb nie fsyncuje katalogu danych.

Weryfikacja (zrobiona, patrz „Wyniki”): `pg_settings` pokazuje wszystkie
wartości z `source = configuration file`, baza `bpp` ma ICU `pl-PL`.

Ryzyko: `autovacuum=off` oznacza brak auto-ANALYZE. Przy małych tabelach
planer i tak szacuje z rozmiaru pliku. Jeśli któryś test zacznie dostawać
patologiczne plany, wycofać tylko tę linię.

### ~~Faza 3 — uwierzytelnianie bez SCRAM~~ — odpada

Obraz ma już `POSTGRES_HOST_AUTH_METHOD=trust`. Przy przejściu na
stockowy obraz (Faza 6) trzeba ustawić tę zmienną jawnie w `postgres_env`.

### Faza 4 — parytet z CI — WDROŻONE (razem z PG18)

`docker-compose.test.yml`, serwis `db`: zamontować ten sam
`docker/test-db/test-fast.sql` jako
`/docker-entrypoint-initdb.d/00-test-fast.sql` (baseline jest już
`01-baseline.sql`) i dodać `POSTGRES_INITDB_ARGS` jak wyżej. Na CI PGDATA jest już na tmpfs, więc P7 nie
dotyczy. Weryfikacja: czasy shardów `Tests (sharded)` przed/po.

### Faza 5 — pomiar końcowy i dokumentacja

1. Powtórzyć pomiary z Fazy 0, uzupełnić tabelę niżej.
2. `CLAUDE.md`, sekcja „Testcontainers": jedna-dwie linie o
   `docker/test-db/test-fast.sql` + przypomnienie, że przy
   `PYTEST_TESTCONTAINERS_REUSE=1` istniejący kontener **nie** dostanie
   nowej konfiguracji — trzeba raz `docker rm -f` własne kontenery
   `bpp_iplweb-tc-{psql,redis}-<gałąź>-…` (po nazwie, nie zbiorczo).
3. Newsfragment: nie dodajemy — zmiana wyłącznie infrastruktury testowej,
   niewidoczna dla użytkowników.

### Faza 6 — poprawki u źródła (osobne repo, osobne wydania)

**Decyzja 2026-11-08: testy i CI przechodzą na `postgres:18.6`** (pkt 2–3 niżej wdrożone bez zmian w pluginie: tuning idzie przez `test-fast.sql`, a nie `postgres_command`). Pierwotny opis: Obraz jest
zamrożony, a repo zarchiwizowane, więc „u źródła” znaczy: **testy i CI
przechodzą na stockowy `postgres:16.13`**. Budowa baseline od zera
zostaje na `iplweb/bpp_dbserver` (plpython, patrz wyżej). Testy nie
potrzebują autotune; lepiej podać jawne, stałe ustawienia.

Warunek wstępny: na stockowym `postgres:16.13` sprawdzić, że ładuje się
`baseline.sql`, przechodzi `make baseline-update` (in-place, bez
plpython) i zielona jest suita. Jeśli którekolwiek padnie, zostajemy
na zamrożonym obrazie z Fazami 1–2 i na tym kończymy.

1. **`pytest-testcontainers-django`**: dodać opcje `postgres_command`
   (dodatkowe argumenty `postgres -c …`), `postgres_tmpfs`,
   `postgres_shm_size`, `redis_command`. Oficjalny entrypoint `postgres`
   przekazuje argumenty `-c` także do serwera tymczasowego używanego przy
   init, więc P1 znika bez żadnego wrappera.
2. **BPP, testy**: `postgres_image = "postgres:16.13"`, w `postgres_env`
   `POSTGRES_INITDB_ARGS` (ICU + `--no-sync`) i
   `POSTGRES_HOST_AUTH_METHOD=trust`, w `postgres_command` pełen zestaw
   z Faz 1–2 (`fsync`, `synchronous_commit`, `full_page_writes`,
   `wal_level=minimal`, `max_wal_senders=0`, `shared_buffers=1GB`,
   `max_connections=250`, `max_locks_per_transaction=512`, `jit=off`,
   `autovacuum=off`, `max_parallel_workers_per_gather=0`), PGDATA na
   tmpfs (P7). Redis z `--save "" --appendonly no`.
3. To samo w `docker-compose.test.yml` (CI). `refresh-baseline.yml` i
   `PG_BASELINE["REBUILD_IMAGE"]` zostają na `iplweb/bpp_dbserver`.
   Komentarz w `settings/base.py` przy `REBUILD_IMAGE` należy poprawić:
   plpython jest potrzebny do migracji od zera, a locale `pl_PL` już nie.
4. Dev (`docker-compose.yml`, `runsite.toml`, gdzie jest `psql-18.3`!)
   to osobna decyzja, poza tym specem.

## Poza zakresem

- ICU `pl-PL` w testach (patrz wyżej) — osobna decyzja.
- `run-site` (`runsite.toml`) — ma własną konfigurację kontenerów; Faza 6.1
  pośrednio go przyspieszy.
- Zmiany liczby workerów xdist.

## Wyniki pomiarów

Laptop (thinkpad, 37,6 GB RAM), przebiegi szeregowe (bez `-n`), świeży
kontener za każdym razem, 3 powtórzenia; „wall" = cały proces `uv run
pytest`, w nawiasie czas raportowany przez pytest. Skrypt i logi:
`pomiar.sh` w scratchpadzie sesji (A = `test_cache.py::test_Autorzy_original`;
B = `mcp_server/tests/test_{auth,routing}.py` +
`test_views/test_seo_metadata.py`, 31 testów `transaction=True`;
C = `raport_slotow/tests/test_views` + `bpp/tests/test_cache`, 115 testów).

| Pomiar | Faza 0 | Po F1 | Po F2 |
|--------|--------|-------|-------|
| A: zimny start, mediana wall (pytest) | 12,8 s (1,9 s) | | |
| B: `transaction=True`, mediana wall (pytest) | 30,0 s (17,6 s) | | |
| C: widoki/cache, mediana wall (pytest) | 31,8 s (20,3 s) | | |
| CI `Tests (sharded)` — najwolniejszy shard (min) | | — | |

Zestawy A/B/C na `postgres:18.6` + `test-fast.sql`: 7,7 s / 24,4 s /
27,1 s wall, czyli tyle samo co Fazy 1–2.

Pełna suita bez Playwright (`-n 12 -m "not playwright"`, laptop 14 rdzeni,
po 1 przebiegu; wszystkie: 11241 passed, 0 failed):

| Wariant | wall | pytest |
|---------|------|--------|
| Dev (16.13, autotune) | 168 s | 154,3 s |
| Fazy 1–2 (16.13 + `test-fast.sql`) | 166 s | 155,7 s |
| `postgres:18.6` + `test-fast.sql` | 158 s / 159 s | 147,3 s / 150,5 s |

Podział CPU w przebiegu PG18 (cgroup `cpu.stat`): workery pytest
1207 CPU-s (średnio 7,6 rdzenia), PG+Redis 453 CPU-s (2,8 rdzenia),
idle 2,6 rdzenia. RAM kontenera PG (max z `memory.stat`): anon 493 MB,
shmem 778 MB, page cache 4,2 GB (pliki baz testowych, do odzyskania).
Opóźnienie `SELECT 1` (psycopg2, 20 tys. zapytań): 27–31 µs przez
zmapowany port (`docker-proxy`), 13–15 µs bezpośrednio na IP kontenera.

`-n 14` vs `-n 12` (PG18, kolejno po sobie): 174 s / 164,7 s wobec
162 s / 151,9 s — **14 workerów jest wolniejsze** (pytest 1352 vs 1211
CPU-s: więcej narzutu startu i rywalizacji o rdzenie, idle spada tylko
z 2,5 do 2,1 rdzenia). Zostajemy przy 12.

Rozkład zimnego startu kontenera (logi `docker logs -t`, Faza 0):
`initdb` 0,6 s → **import `00-baseline.sql` 4,9 s** (fsync=on, P1) →
checkpoint przy zamknięciu serwera tymczasowego 0,55 s → start docelowego
serwera. Pozostałe ~4 s różnicy wall−pytest to start Pythona/Django/pytest
(poza zakresem tego specu).

Zrzut konfiguracji z Fazy 0 (`pg_settings`, zamrożony obraz):
`shared_buffers≈9,4GB` (1 172 304 × 8 kB), `effective_cache_size≈28GB`, `maintenance_work_mem=2GB`,
`work_mem=9378kB`, `max_connections=250`, `max_locks=512`,
`max_parallel_workers_per_gather=4`, `jit=on`, `autovacuum=on`,
`fsync/synchronous_commit/full_page_writes=off`. Baza `bpp`: ICU `pl-PL`,
32 MB, języki: `internal, c, sql, plpgsql` (bez `plpython3u`).

## Profil pełnej suity i poprawki po stronie testów (2026-11-08)

Profil: py-spy na wszystkich workerach (`-n 12`, PG18) + `pg_stat_statements`.
Udział w czasie aktywnej pracy workerów (inclusive, nakładają się):

| Pozycja | Udział | Co zrobiono |
|---------|--------|-------------|
| fixture `charaktery_formalne` (delete + ponowne wstawienie 27 rekordów MPTT w każdym teście) | ~13% | aktualizacja w miejscu jednym `bulk_update`; stara ścieżka tylko gdy rekordów brakuje (po TRUNCATE) |
| zbieranie testów w każdym workerze | ~15% | — (do zbadania: importy na poziomie modułów) |
| flush po testach transakcyjnych (196 × TRUNCATE ~266 ms + reinstalacja triggerów denorm: 34 tys. DROP TRIGGER, 32 tys. CREATE) | ~10% | reinstalacja triggerów denorm odpięta na czas flusha (`src/conftest.py`) |
| easyaudit (sygnały `pre_save`/`post_save`) | ~9% | **zostaje** — bez niego w testach psuły się rzeczy, które potem padały na produkcji |
| GC (`gc-steward` co 25 testów + `gc_collect_harder` pytesta) | ~8% | `gc_steward_every = 100` |
| roundtripy do PG przez `docker-proxy` (1,65 mln zapytań, w tym 566 tys. SAVEPOINT/RELEASE) | ~2 s suity | — (za mały zysk) |
| Redis | 1234 komendy na całą suitę | — |

Przy okazji: fixture ustawiał `charakter_ogolny = ROZDZIAL` na obiekcie
książki (KSP, już zapisanym) zamiast rozdziału (ROZ) — naprawione.

Wynik (pełna suita bez Playwright, `-n 12`, PG18, 11241 passed):

| | pytest | wall | RSS workerów (peak) |
|---|---|---|---|
| przed (3 przebiegi) | 147,3 / 150,5 / 151,9 s | 158–162 s | 585–664 MB |
| po (2 przebiegi) | 137,5 / 125,7 s | 149 / 138 s | 602–698 MB |

## Leniwe importy ciężkich bibliotek (2026-11-08)

Korekta: zbieranie testów to ~6,7% czasu workerów (~5 s na workera), nie
~15% — pierwszy klasyfikator profilu liczył do „zbierania" także GC. Samo
zbieranie to w większości praca pytest (budowa 11 tys. obiektów testów),
nie do urwania po stronie projektu.

Za to start aplikacji (`django.setup()` + URLconf + Celery z taskami,
`-X importtime`) wciągał biblioteki potrzebne pojedynczym widokom/taskom.
Przeniesione do funkcji, które ich używają:

| Biblioteka | Koszt | Gdzie był import |
|---|---|---|
| OR-Tools (+ pandas) | ~0,23 s | `ewaluacja_optymalizacja/tasks/optimization.py` |
| WeasyPrint (`django_weasyprint`) | ~0,22 s | `raport_slotow/views/autor.py` |
| pandas + numpy | ~0,19 s | `import_polon/utils.py` |
| xhtml2pdf (+ reportlab, pypdf, fontTools) | ~0,10 s | `oswiadczenia/tasks.py` (`_pisa()`) |
| idutils | ~0,09 s | `zglos_publikacje/identyfikatory.py` |

Start aplikacji: 1,70 s → 1,18 s, modułów 5022 → 4182. Strażnik:
`src/django_bpp/tests/test_leniwe_importy.py` (start w osobnym procesie,
`sys.modules` nie może zawierać tych pakietów). Ścieżki z leniwym importem
mają testy, które je faktycznie wykonują (PDF oświadczeń: nowe testy w
`src/oswiadczenia/tests.py`). Zostaje openpyxl (+ numpy, ~0,08 s):
importowany na górze 18 modułów, w tym zawsze ładowanych — za duży diff
jak na zysk.

Pełna suita (`-n 12`): 127,7 s — w szumie względem 125,7–137,5 s, bo na
workera to ~0,5 s. Zysk jest na starcie procesów, nie w czasie testów.
