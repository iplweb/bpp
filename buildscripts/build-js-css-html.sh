#!/bin/bash -e


pushd `dirname $0` > /dev/null
SCRIPTPATH=`pwd -P`
popd > /dev/null

cd $SCRIPTPATH/..

grunt build > /dev/null
rm -rf $SCRIPTPATH/src/django_bpp/staticroot
python src/manage.py collectstatic --noinput -v0
python src/manage.py compress --force -v0
