#!/bin/bash -e

if [ -z "$VIRTUAL_ENV" ]; then
    echo "Ten skrypt dziala spod virtualenv, aktywuj jakies"
    exit 1
fi

cd ..
make clean
bumpversion patch

export PWD=`pwd`
export CURDIR=`basename $PWD`

cd ..
rm -rf django_bpp-release
cp -R $CURDIR django_bpp-release

cd django_bpp-release
rm -rf src/django_bpp/node_modules files .git src/django_bpp/components Vagrantfile Makefile provisioning deployment/node_modules .idea .vagrant
export VERSION=`python src/django_bpp/django_bpp/version.py`

cd ..
mv django_bpp-release django_bpp-release-$VERSION

tar -czvf django_bpp-release-$VERSION.tgz django_bpp-release-$VERSION

rm -rf django_bpp-release-$VERSION