#!/bin/sh -e

export PGUSER="${DJANGO_BPP_DB_USER}"
export PGHOST="${DJANGO_BPP_DB_HOST}"
export PGPORT="${DJANGO_BPP_DB_PORT}"
export PGPASSWORD="${DJANGO_BPP_DB_PASSWORD}"

cd /app

# === PHASE 1: Migration (BLOCKING) ===
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
        --reload-dir /app/src django_bpp.asgi:application
else
    exec uv run uvicorn --host 0 --port 8000 django_bpp.asgi:application
fi
