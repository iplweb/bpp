#!/usr/bin/env bash
set -e

CMD="${1:-web}"

echo "==> migrate"
python manage.py migrate --noinput

echo "==> seed_demo"
python manage.py seed_demo

if [ "$CMD" = "worker" ]; then
    echo "==> celery worker"
    exec celery -A demo_project worker --loglevel=info
else
    echo "==> collectstatic"
    python manage.py collectstatic --noinput
    echo "==> daphne on :8000"
    exec daphne -b 0.0.0.0 -p 8000 demo_project.asgi:application
fi
