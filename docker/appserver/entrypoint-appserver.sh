#!/bin/sh -e

export PGUSER="${DJANGO_BPP_DB_USER}"
export PGHOST="${DJANGO_BPP_DB_HOST}"
export PGPORT="${DJANGO_BPP_DB_PORT}"
export PGPASSWORD="${DJANGO_BPP_DB_PASSWORD}"

cd /app

# === PHASE 1: Migration (BLOCKING) ===
# On a completely empty database (`django_migrations` does not exist
# yet) load the baseline pg_dump first — that turns 800+ migrations
# into a few-second SQL import, after which `migrate` only needs to
# apply the small delta of migrations added since the dump was last
# regenerated. Existing production databases always have
# `django_migrations`, so this branch is a no-op for them.
NEEDS_BASELINE=$(psql -d "${DJANGO_BPP_DB_NAME}" -tAc \
    "SELECT to_regclass('public.django_migrations') IS NULL")
if [ "$NEEDS_BASELINE" = "t" ] && [ -f /app/baseline/baseline.sql ]; then
    echo "Empty database detected — loading baseline dump..."
    psql -d "${DJANGO_BPP_DB_NAME}" \
        -v ON_ERROR_STOP=1 --single-transaction \
        -f /app/baseline/baseline.sql
    echo "Baseline loaded."
fi

echo "Database migrations..."
uv run src/manage.py migrate
echo "Migrations done."

# === PHASE 2: Background tasks ===
echo "Starting background tasks..."
(
    echo "  [bg] collectstatic..."
    uv run src/manage.py collectstatic --noinput -v0 --traceback
    echo "  [bg] collectstatic done."

    echo "  [bg] compress..."
    uv run src/manage.py compress -v0 --force --traceback
    echo "  [bg] compress done."

    echo "  [bg] generate_500_page..."
    uv run src/manage.py generate_500_page
    echo "  [bg] generate_500_page done."

    echo "  [bg] All background tasks completed."
) &

# === PHASE 3: Start server (immediately) ===
echo "Starting uvicorn..."
if [ "$ENABLE_AUTORELOAD_ON_CODE_CHANGE" = "1" ] || \
   [ "$ENABLE_AUTORELOAD_ON_CODE_CHANGE" = "true" ]; then
    echo "Auto-reload ENABLED"
    uv pip install watchdog --quiet
    exec uv run uvicorn --host 0 --port 8000 --reload \
        --reload-dir /app/src \
        --log-config /uvicorn_log_config.json \
        django_bpp.asgi:application
else
    exec uv run uvicorn --host 0 --port 8000 \
        --log-config /uvicorn_log_config.json \
        django_bpp.asgi:application
fi
