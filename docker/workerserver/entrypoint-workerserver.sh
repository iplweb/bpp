#!/bin/sh -e

cd /app

CELERY_QUEUE=${CELERY_QUEUE:-celery,denorm}

if [ "$ENABLE_AUTORELOAD_ON_CODE_CHANGE" = "1" ] || [ "$ENABLE_AUTORELOAD_ON_CODE_CHANGE" = "true" ]; then
    echo "Auto-reload ENABLED for worker"
    exec watchmedo auto-restart --directory=/app/src --pattern=*.py --recursive --ignore-patterns '__pycache__/*;*.pyc' -- celery -A django_bpp.celery_tasks worker -Q $CELERY_QUEUE
else
    exec celery -A django_bpp.celery_tasks worker -Q $CELERY_QUEUE
fi
