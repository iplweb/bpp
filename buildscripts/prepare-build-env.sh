#!/bin/bash -e

#
# Ten skrypt przygotowywuje do budowania django-bpp
#

if [ -z "$VIRTUAL_ENV" ]; then
    echo "Ten skrypt dziala spod virtualenv, aktywuj jakies"
    exit 1
fi

if [ -z "$DJANGO_SETTINGS_MODULE" ]; then
    echo "Ustaw zmienna DJANGO_SETTINGS_MODULE, bo sie nie uda..."
    exit 1
fi

pushd `dirname $0` > /dev/null
SCRIPTPATH=`pwd -P`
popd > /dev/null

cd $SCRIPTPATH/../src

npm --quiet install grunt grunt-sass grunt-contrib-watch grunt-contrib-qunit

rm -rf components/bower_components staticroot
yes n | python manage.py bower_install -F
echo "2" |python manage.py bower install "jquery#2.2.4"

python manage.py collectstatic --noinput

grunt build

dropdb --if-exists bpp
createdb bpp 

python manage.py migrate --noinput
python manage.py compress --force
