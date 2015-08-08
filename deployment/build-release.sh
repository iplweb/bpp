#!/bin/bash -e

if [ -z "$VIRTUAL_ENV" ]; then
    echo "Ten skrypt dziala spod virtualenv, aktywuj jakies"
    exit 1
fi

cd ..
make clean

export PWD=`pwd`
export CURDIR=`basename $PWD`

cd ..
rm -rf django-bpp-release
cp -R $CURDIR django-bpp-release

cd django-bpp-release
rm -rf src/django_bpp/node_modules files .git src/django_bpp/components Vagrantfile Makefile provisioning deployment/node_modules .idea .vagrant
export VERSION=`python src/django_bpp/django_bpp/version.py`

cd ..
mv django-bpp-release django-bpp-release-$VERSION

tar -czvf django-bpp-release-$VERSION.tgz django-bpp-release-$VERSION

rm -rf django-bpp-release-$VERSION