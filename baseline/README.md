# Baseline `pg_dump` for fast database bootstrapping

This directory holds a frozen `pg_dump` of a fresh bpp database after
all migrations have been applied. Loading it into an empty database
takes seconds, instead of the minutes needed to run 800+ Django
migrations from scratch.

## How it works

1. `baseline.sql` — plain SQL dump produced by `pg_dump` against a
   clean database that has just finished `migrate`. Includes:
   - schema (tables, indexes, triggers, custom functions in
     `plpython3u`, materialized views)
   - bootstrap data inserted by historical data-migrations
     (`Charakter_Formalny`, `Jezyk`, `Typ_KBN`, …)
   - the `django_migrations` table with every applied migration name
     — this is what tells Django "the schema is already at version N,
     don't replay anything below it"
   - **no user-generated data** — only what `migrate` produces on a
     clean DB

2. `baseline.meta.json` — sidecar metadata recording when the dump
   was generated, the git SHA, and the highest migration name per app.
   Used by `check_freshness.py` to gate stale dumps in CI.

3. The pytest test runner (via `src/conftest.py`) and the production
   container entrypoint (`docker/appserver/entrypoint-appserver.sh`)
   both detect "is this DB empty?" by querying
   `to_regclass('public.django_migrations')`. If empty AND
   `baseline.sql` exists, they `psql -f baseline.sql` first, then run
   `migrate` to apply any newer migrations on top. Existing databases
   (production, long-lived dev DBs) skip the load entirely — the
   feature is opt-in by construction.

## When to regenerate

Whenever migrations are added to any app and merged to `main`. A
GitHub Action (`.github/workflows/refresh-baseline.yml`) regenerates
the dump automatically when `src/**/migrations/**` is touched in a
push to `main`. Manual regeneration:

    make rebuild-baseline

That target spins up an isolated PostgreSQL container on port 55433
(see `docker-compose.baseline.yml`), runs `migrate` against it,
`pg_dump`s the result, writes `baseline.sql` and `baseline.meta.json`,
and tears the container down.

After running, commit both files together:

    git add baseline/baseline.sql baseline/baseline.meta.json
    git commit -m "chore(baseline): refresh pg_dump after migrations 0411..0413"

## When CI fails on `check_freshness.py`

CI runs:

    uv run python baseline/check_freshness.py --max-delta 50

If any app has more than 50 migrations newer than the baseline, the
build fails. Run `make rebuild-baseline`, commit, push.

## Troubleshooting

### `psql: extension "plpython3u" requires superuser`

The `iplweb/bpp_dbserver` Docker image runs PostgreSQL with the
default `postgres` superuser, so `CREATE EXTENSION plpython3u` works
during a `make rebuild-baseline`. If you regenerate against a
different PostgreSQL build, your role must be a superuser **or** the
extension must already be installed in the target database.

### `psql: ERROR: could not create locale "pl_PL.UTF-8"`

The dump's `CREATE COLLATION "pl_PL"(locale='pl_PL.UTF-8')` requires
the OS locale to exist in the container. The `iplweb/bpp_dbserver`
image generates it at build time. On a vanilla `postgres:16` you'd
need:

    apt-get install -y locales && locale-gen pl_PL.UTF-8

### "Empty database" detection fires on a non-empty database

The check uses `SELECT to_regclass('public.django_migrations')`. The
only way it returns NULL on a non-empty DB is if someone manually
dropped that table. Don't do that.

### Dump grew past 50 MB

Plain SQL works well up to ~50 MB in git history. Past that, consider
gzip (`gzip -9 baseline.sql`, update load helpers) or git LFS. Open a
discussion before flipping the format — the load helpers and the
production entrypoint both assume plain SQL today.

## Layout

| File | Purpose |
| --- | --- |
| `baseline.sql` | The dump (committed to git, plain SQL, ~5–15 MB expected) |
| `baseline.meta.json` | Sidecar metadata (committed to git) |
| `load_baseline.py` | Subprocess helper used by conftest + management command |
| `write_meta.py` | `make rebuild-baseline` invokes this to regenerate the meta sidecar |
| `check_freshness.py` | CI gate; exits 1 when delta exceeds threshold |
| `README.md` | This file |
