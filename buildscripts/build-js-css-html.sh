#!/bin/bash -e

grunt build
python src/manage.py collectstatic --noinput
python src/manage.py compress --force
