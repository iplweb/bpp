#!/bin/bash -e

#
# Ten skrypt przygotowywuje do budowania django-bpp
#

NO_REBUILD=0

while test $# -gt 0
do
    case "$1" in
        --no-rebuild) NO_REBUILD=1
            ;;
	--help) echo "--no-rebuild"
	    exit 1
	    ;;
        --*) echo "bad option $1"
	    exit 1
            ;;
    esac
    shift
done

pushd `dirname $0` > /dev/null
SCRIPTPATH=`pwd -P`
popd > /dev/null

cd $SCRIPTPATH/..

export PATH=$PATH:./node_modules/.bin/

sudo npm install -g bower grunt-cli
npm install grunt grunt-sass grunt-contrib-watch grunt-contrib-qunit 

rm -rf src/components/bower_components src/django_bpp/staticroot
yes n | python src/manage.py bower_install -F
echo "2" |python src/manage.py bower install "jquery#2.1.4"

grunt build

python src/manage.py collectstatic --noinput

python src/manage.py compress --force
