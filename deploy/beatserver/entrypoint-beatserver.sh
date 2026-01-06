#!/bin/sh -e

cd /app

if [ "$ENABLE_AUTORELOAD_ON_CODE_CHANGE" = "1" ] || [ "$ENABLE_AUTORELOAD_ON_CODE_CHANGE" = "true" ]; then
    echo "Auto-reload ENABLED for beat"
    echo "Installing watchdog for auto-reload functionality..."
    uv pip install watchdog --quiet
    exec uv run watchmedo auto-restart --directory=/app/src --pattern=*.py --recursive --ignore-patterns '__pycache__/*;*.pyc' -- uv run celery -A django_bpp.celery_tasks beat --pidfile=/celerybeat.pid -s /celerybeat-schedule
else
    echo "Auto-reload DISABLED for beat"
    exec uv run celery -A django_bpp.celery_tasks beat --pidfile=/celerybeat.pid -s /celerybeat-schedule
fi
