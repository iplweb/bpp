#!/bin/bash -e

. /etc/lsb-release


cd /home/vagrant
OUTDIR=dependencies-$DISTRIB_ID-$DISTRIB_RELEASE-`date +%Y%m%d`

rm -rf $OUTDIR
mkdir $OUTDIR
mkdir -p /vagrant/releases || true

pip --quiet download -r django-bpp/requirements/`uname`.requirements.txt --no-index --find-links=/vagrant/buildscripts/DIST -d $OUTDIR
pip --quiet download -r django-bpp/requirements/requirements.txt --no-index --find-links=/vagrant/buildscripts/DIST -d $OUTDIR

tar -cf $OUTDIR.tar $OUTDIR
cp $OUTDIR.tar /vagrant/releases
