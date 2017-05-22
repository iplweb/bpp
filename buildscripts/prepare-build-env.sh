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


if [ "$NO_REBUILD" == "0" ]; then
    # Nie przebudowuj bazy danych 
    dropdb --if-exists bpp
    createdb bpp 
    python src/manage.py migrate --noinput
    dropdb --if-exists test_bpp
    createdb test_bpp --template=bpp

    export GIT_BRANCH_NAME=`git status |grep "On branch"|sed "s/On branch //"`
    stellar replace $GIT_BRANCH_NAME || stellar snapshot $GIT_BRANCH_NAME
fi

python src/manage.py compress --force
