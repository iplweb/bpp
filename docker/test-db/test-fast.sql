-- Konfiguracja serwera PostgreSQL dla KONTENERÓW TESTOWYCH. NIGDY na produkcji:
-- fsync=off itd. oznacza utratę danych przy awarii.
--
-- Montowany przez pytest-testcontainers-django jako PIERWSZY skrypt
-- w /docker-entrypoint-initdb.d/ (przed baseline.sql; patrz
-- [tool.pytest-testcontainers-django] w pyproject.toml). Spec:
-- docs/deweloper/spec-testcontainers-pg-szybciej-2026-11.md
--
-- Dlaczego ALTER SYSTEM w skrypcie init:
-- * entrypoint obrazu ładuje skrypty init na serwerze TYMCZASOWYM, który
--   startuje z domyślną konfiguracją (fsync=on). Parametry `sighup` niżej
--   + pg_reload_conf() działają od razu, więc import baseline.sql idzie już
--   bez fsync;
-- * ALTER SYSTEM zapisuje postgresql.auto.conf, czytany PO postgresql.conf
--   (łącznie z include autotune w iplweb/bpp_dbserver), więc te wartości
--   wygrywają z autotune i obowiązują w docelowym serwerze po restarcie.
--   Parametry `postmaster` (shared_buffers, max_connections, wal_level...)
--   wchodzą właśnie przy tym restarcie;
-- * nie zależymy od autotune obrazu (który liczy pamięć z RAM-u HOSTA, bo
--   testcontainers nie ustawia limitu kontenera → shared_buffers ~11 GB dla
--   bazy 32 MB), więc ten sam plik działa też na stockowym `postgres`.

-- sighup: obowiązują od razu (import baseline).
ALTER SYSTEM SET fsync = off;
ALTER SYSTEM SET synchronous_commit = off;
ALTER SYSTEM SET full_page_writes = off;

-- WAL: zero replikacji/archiwizacji, rzadkie checkpointy.
ALTER SYSTEM SET wal_level = minimal;
ALTER SYSTEM SET max_wal_senders = 0;
ALTER SYSTEM SET archive_mode = off;
ALTER SYSTEM SET max_wal_size = '4GB';
ALTER SYSTEM SET checkpoint_timeout = '30min';

-- Pamięć: baza testowa ma kilkadziesiąt MB. Duże shared_buffers spowalnia
-- każdy commit z TRUNCATE/DROP (pełny skan buforów poza recovery).
ALTER SYSTEM SET shared_buffers = '1GB';
ALTER SYSTEM SET effective_cache_size = '3GB';
ALTER SYSTEM SET maintenance_work_mem = '256MB';
ALTER SYSTEM SET work_mem = '8MB';

-- Połączenia / locki: xdist z wieloma workerami tworzy i dropuje setki
-- tabel i indeksów w jednej transakcji (domyślne 64 locki to za mało).
ALTER SYSTEM SET max_connections = 250;
ALTER SYSTEM SET max_locks_per_transaction = 512;

-- Planer / wykonanie: małe dane, CPU wysycone przez workery xdist.
ALTER SYSTEM SET jit = off;
ALTER SYSTEM SET max_parallel_workers_per_gather = 0;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET autovacuum = off;

-- Na serwerze tymczasowym reload zaloguje "configuration file ... contains
-- errors; unaffected changes were applied" — to tylko parametry postmaster
-- (shared_buffers, max_connections, wal_level...), których nie da się zmienić
-- bez restartu. Wchodzą przy starcie docelowego serwera; nie jest to błąd.
SELECT pg_reload_conf();
