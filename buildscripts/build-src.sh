#!/bin/bash -e

cd /home/vagrant/django-bpp/src

rm -rf staticroot
grunt build
python manage.py collectstatic --noinput -v 0
python manage.py compress --force -v 0

VERSION=`python django_bpp/version.py`

cd ..
mkdir -p /vagrant/releases || true
tar --exclude=src/media --exclude=*.pyc --exclude=__pycache__ --exclude=src/.cache --exclude=src/node_modules --exclude=src/components -cjf /vagrant/releases/release-$VERSION.tbz2 src
