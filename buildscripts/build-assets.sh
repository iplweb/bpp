#!/bin/bash -e


pushd `dirname $0` > /dev/null
SCRIPTPATH=`pwd -P`
popd > /dev/null

cd $SCRIPTPATH/..

yarn install 

python src/manage.py bower_install -RF
echo "2" |python src/manage.py bower install "jquery#2.1.4" -- --allow-root

npm rebuild sass grunt-sass
grunt build 
rm -rf $SCRIPTPATH/src/django_bpp/staticroot
python src/manage.py collectstatic --noinput 
python src/manage.py compress --force 
