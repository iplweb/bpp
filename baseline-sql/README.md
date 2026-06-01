# Baseline `pg_dump` for fast database bootstrapping

This directory holds a frozen `pg_dump` of a fresh bpp database after
all migrations have been applied. Loading it into an empty database
takes seconds, instead of the minutes needed to run 800+ Django
migrations from scratch.

All logic lives in the reusable Django app `src/django_pg_baseline/`.
This directory is just a data sidecar (`baseline.sql` +
`baseline.meta.json`).

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

2. `baseline.meta.json` — sidecar metadata recording the git SHA and
   the highest migration name per app. Used by `baseline_check` to
   gate stale dumps in CI.

3. The pytest test runner and the production container entrypoint
   both rely on the `django_pg_baseline` app:
   - `DjangoPgBaselineConfig.ready()` installs a monkey patch on
     `_create_test_db` that `psql -f`'s `baseline.sql` into each
     fresh test database.
   - The appserver entrypoint calls `manage.py baseline_load`, which
     is a no-op on non-empty databases.

## Commands

Run from the repository root:

    # Regenerate baseline.sql + baseline.meta.json (needs testcontainers)
    uv sync --extra baseline-rebuild
    uv run python src/manage.py baseline_rebuild
    # or:
    make rebuild-baseline

    # Load baseline into the configured DB (no-op if not empty)
    uv run python src/manage.py baseline_load [--database ALIAS] [--force]

    # Informational (always exits 0) — pokazuje per-app delty bez gate'a
    uv run python src/manage.py baseline_check

    # CI gate — exit 1 when any app has more than --max-delta new migrations.
    # Hard-fail (exit 1) gdy baseline.sql lub baseline.meta.json brakuje.
    uv run python src/manage.py baseline_check --max-delta 50

    # Human-readable summary of the current baseline state
    uv run python src/manage.py baseline_info

## When to regenerate

Whenever migrations are added and merged to `dev`. A GitHub Action
(`.github/workflows/refresh-baseline.yml`) regenerates the dump
automatically when `src/**/migrations/**` is touched in a push to
`dev`. After a manual regeneration, commit both files together:

    git add baseline-sql/baseline.sql baseline-sql/baseline.meta.json
    git commit -m "chore(baseline): refresh pg_dump after migrations …"

## Configuration

`settings.PG_BASELINE` (see `src/django_bpp/settings/base.py`) drives
every knob: paths, the rebuild image, pg_dump args, the freshness
threshold, and the list of timestamp columns to "freeze" for a
deterministic diff.

## Troubleshooting

### `psql: extension "plpython3u" requires superuser`

The `iplweb/bpp_dbserver` Docker image runs PostgreSQL with the
default `postgres` superuser, so `CREATE EXTENSION plpython3u` works
during a `baseline_rebuild`. If you regenerate against a different
PostgreSQL build, your role must be a superuser **or** the extension
must already be installed in the target database.

### `psql: ERROR: could not create locale "pl_PL.UTF-8"`

The dump's `CREATE COLLATION "pl_PL"(locale='pl_PL.UTF-8')` requires
the OS locale to exist in the container. The `iplweb/bpp_dbserver`
image generates it at build time. On a vanilla `postgres:16` you'd
need:

    apt-get install -y locales && locale-gen pl_PL.UTF-8

### Dump grew past 50 MB

Plain SQL works well up to ~50 MB in git history. Past that, consider
gzip or git LFS. Open a discussion before flipping the format — the
loader and the production entrypoint both assume plain SQL today.

## Layout

| File | Purpose |
| --- | --- |
| `baseline.sql` | The dump (committed to git, plain SQL) |
| `baseline.meta.json` | Sidecar metadata (committed to git) |
| `README.md` | This file |
