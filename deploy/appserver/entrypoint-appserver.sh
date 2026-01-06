#!/bin/sh -e

export PGUSER="${DJANGO_BPP_DB_USER}"
export PGHOST="${DJANGO_BPP_DB_HOST}"
export PGPORT="${DJANGO_BPP_DB_PORT}"
export PGPASSWORD="${DJANGO_BPP_DB_PASSWORD}"

cd /app

echo -n "Creating database ${DJANGO_BPP_DB_NAME}, if not exists... "
echo "SELECT 'CREATE DATABASE ${DJANGO_BPP_DB_NAME}' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DJANGO_BPP_DB_NAME}')\gexec" | psql template1
echo "done."

echo -n "Database migrations, if any... "
uv run src/manage.py migrate
echo "done."

echo -n "Update 500.html page... "
uv run src/manage.py generate_500_page
echo "done."

echo -n "Running collectstatic and compress... "
uv run src/manage.py collectstatic --noinput -v0 --traceback
uv run src/manage.py compress -v0 --force --traceback
echo "done."

echo "Starting uvicorn... "
if [ "$ENABLE_AUTORELOAD_ON_CODE_CHANGE" = "1" ] || [ "$ENABLE_AUTORELOAD_ON_CODE_CHANGE" = "true" ]; then
    echo "Auto-reload ENABLED"
    echo "Installing watchdog for auto-reload functionality..."
    uv pip install watchdog --quiet
    uv run uvicorn --host 0 --port 8000 --reload --reload-dir /app/src django_bpp.asgi:application
else
    echo "Auto-reload DISABLED"
    uv run uvicorn --host 0 --port 8000 django_bpp.asgi:application
fi
