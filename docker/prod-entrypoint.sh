#!/bin/bash -e

export DJANGO_SETTINGS_MODULE=django_bpp.settings.production

echo "Waiting 5 seconds for PostgreSQL to start..."
sleep 5 

createdb || true

echo "------------------------------------------------------------------------------"
echo "Current settings: "
echo "------------------------------------------------------------------------------"
set | grep DJANGO_BPP

echo -n "Running migrate... "
bpp-manage.py migrate -v0
echo "done!" 

export C_FORCE_ROOT=TRUE
celery worker --config=$DJANGO_SETTINGS_MODULE -DA django_bpp.celery_tasks &

bpp-manage.py runserver 0.0.0.0:8000
