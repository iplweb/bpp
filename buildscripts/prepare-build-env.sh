#!/bin/bash -e

# Ten skrypt przygotowywuje do budowania django-bpp

pushd `dirname $0` > /dev/null
SCRIPTPATH=`pwd -P`
popd > /dev/null

cd $SCRIPTPATH/..

yarn install

rm -rf src/components/bower_components src/django_bpp/staticroot
python src/manage.py bower_install -F
echo "2" |python src/manage.py bower install "jquery#2.1.4"
