#!/bin/sh -e
#
# Lightweight auth server entrypoint
# Starts quickly - no migrations, no collectstatic, no compress
#

cd /app

echo "Starting gunicorn auth server on port 8001..."
exec gunicorn \
    --bind 0.0.0.0:8001 \
    --workers 2 \
    --timeout 30 \
    --config /gunicorn_conf.py \
    django_bpp.wsgi_auth_server:application
