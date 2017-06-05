#!/bin/bash -e

export DJANGO_SETTINGS_MODULE=django_bpp.settings.local

echo "Waiting 5 seconds for PostgreSQL to start..."
sleep 5 

createdb || true

echo "------------------------------------------------------------------------------"
echo "Current settings: "
echo "------------------------------------------------------------------------------"
set | grep DJANGO_BPP

echo -n "Running migrate... "
~/.virtualenvs/env-bpp/bin/bpp-manage.py migrate -v0
echo "done!" 

export C_FORCE_ROOT=TRUE
~/.virtualenvs/env-bpp/bin/celery worker --config=$DJANGO_SETTINGS_MODULE -DA django_bpp.celery_tasks &

~/.virtualenvs/env-bpp/bin/bpp-manage.py runserver 0.0.0.0:8000
