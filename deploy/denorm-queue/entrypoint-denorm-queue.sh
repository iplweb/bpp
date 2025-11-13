#!/bin/sh -e

cd /app

if [ "$ENABLE_AUTORELOAD_ON_CODE_CHANGE" = "1" ] || [ "$ENABLE_AUTORELOAD_ON_CODE_CHANGE" = "true" ]; then
    echo "Auto-reload ENABLED for denorm-queue"
    echo "Installing watchdog for auto-reload functionality..."
    uv pip install watchdog --quiet
    exec uv run watchmedo auto-restart --directory=/app/src --pattern=*.py --recursive -- python src/manage.py denorm_queue
else
    echo "Auto-reload DISABLED for denorm-queue"
    exec uv run python src/manage.py denorm_queue
fi
