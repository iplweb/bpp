#!/bin/sh -e

cd /app

if [ "$ENABLE_AUTORELOAD_ON_CODE_CHANGE" = "1" ] || [ "$ENABLE_AUTORELOAD_ON_CODE_CHANGE" = "true" ]; then
    echo "Auto-reload ENABLED for beat"
    exec watchmedo auto-restart --directory=/app/src --pattern=*.py --recursive --ignore-patterns '__pycache__/*;*.pyc' -- celery -A django_bpp.celery_tasks beat -S django_bpp.beat_heartbeat:HeartbeatScheduler --pidfile=/celerybeat.pid -s /celerybeat-schedule
else
    exec celery -A django_bpp.celery_tasks beat -S django_bpp.beat_heartbeat:HeartbeatScheduler --pidfile=/celerybeat.pid -s /celerybeat-schedule
fi
