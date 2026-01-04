#!/bin/sh -e

cd /app

CELERY_QUEUE=${CELERY_QUEUE:-celery}

if [ "$ENABLE_AUTORELOAD_ON_CODE_CHANGE" = "1" ] || [ "$ENABLE_AUTORELOAD_ON_CODE_CHANGE" = "true" ]; then
    echo "Auto-reload ENABLED for worker"
    echo "Installing watchdog for auto-reload functionality..."
    uv pip install watchdog --quiet
    exec uv run watchmedo auto-restart --directory=/app/src --pattern=*.py --recursive --ignore-patterns '__pycache__/*;*.pyc' -- uv run celery -A django_bpp.celery_tasks worker -Q $CELERY_QUEUE
else
    echo "Auto-reload DISABLED for worker"
    exec uv run celery -A django_bpp.celery_tasks worker -Q $CELERY_QUEUE
fi
