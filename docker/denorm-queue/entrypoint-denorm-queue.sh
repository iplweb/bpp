#!/bin/sh -e

cd /app

if [ "$ENABLE_AUTORELOAD_ON_CODE_CHANGE" = "1" ] || [ "$ENABLE_AUTORELOAD_ON_CODE_CHANGE" = "true" ]; then
    echo "Auto-reload ENABLED for denorm-queue"
    exec watchmedo auto-restart --directory=/app/src --pattern=*.py --recursive --ignore-patterns '__pycache__/*;*.pyc' -- python src/manage.py denorm_queue
else
    exec python src/manage.py denorm_queue
fi
