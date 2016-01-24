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

npm --quiet install grunt-sass grunt-contrib-watch grunt-contrib-qunit

yes n | python manage.py bower_install -F
python manage.py collectstatic --noinput

grunt build

python manage.py migrate --noinput
python manage.py compress --force
