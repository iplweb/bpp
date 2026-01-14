#!/bin/sh -e
#
# Lightweight auth server entrypoint
# Starts quickly - no migrations, no collectstatic, no compress
#

cd /app

# Wait for database to be ready
echo "Waiting for database at ${DJANGO_BPP_DB_HOST}:${DJANGO_BPP_DB_PORT}..."
export PGPASSWORD="${DJANGO_BPP_DB_PASSWORD}"
until psql -h "${DJANGO_BPP_DB_HOST}" -U "${DJANGO_BPP_DB_USER}" \
    -p "${DJANGO_BPP_DB_PORT}" -d "${DJANGO_BPP_DB_NAME}" \
    -c "SELECT 1" > /dev/null 2>&1; do
    echo "Database not ready, waiting..."
    sleep 1
done
echo "Database ready."

# Wait for Redis to be ready
echo "Waiting for Redis at ${DJANGO_BPP_REDIS_HOST}:${DJANGO_BPP_REDIS_PORT}..."
until nc -z "${DJANGO_BPP_REDIS_HOST}" "${DJANGO_BPP_REDIS_PORT}"; do
    echo "Redis not ready, waiting..."
    sleep 1
done
echo "Redis ready."

echo "Starting gunicorn auth server on port 8001..."
exec uv run gunicorn \
    --bind 0.0.0.0:8001 \
    --workers 2 \
    --timeout 30 \
    --access-logfile - \
    --error-logfile - \
    django_bpp.wsgi_auth_server:application
