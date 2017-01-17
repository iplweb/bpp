#!/bin/bash -e

mkdir -p /vagrant/releases || true

cd $HOME/django-bpp/src

rm -rf staticroot
./node_modules/.bin/grunt build
python manage.py collectstatic --noinput -v 0
python manage.py compress --force -v 0

VERSION=`python django_bpp/version.py`

cd ../..

OUTDIR=django-bpp-$VERSION
rm -rf $OUTDIR

cp -R django-bpp $OUTDIR

rm -rf $OUTDIR/src/media
rm -rf $OUTDIR/src/.cache
rm -rf $OUTDIR/src/node_modules
rm -rf $OUTDIR/src/components
rm -rf $OUTDIR/.git $OUTDIR/.gitignore $OUTDIR/Makefile $OUTDIR/provisioning $OUTDIR/requirements/Darwin.requirements.txt
rm -rf $OUTDIR/files $OUTDIR/requirements/src.requirements.txt $OUTDIR/requirements/dev.requirements.txt
rm -rf $OUTDIR/ansible $OUTDIR/fabfile.py $OUTDIR/.bumpversion.cfg
rm -rf $OUTDIR/buildscripts

tar --exclude=*.pyc --exclude=__pycache__ -cjf /vagrant/releases/release-$VERSION.tbz2 $OUTDIR
