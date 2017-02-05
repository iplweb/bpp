#!/bin/bash -e


if [ -z "$VIRTUAL_ENV" ]; then
    echo "Ten skrypt dziala spod virtualenv, aktywuj jakies"
    exit 1
fi

if [ -z "$DJANGO_SETTINGS_MODULE" ]; then
    echo "Ustaw zmienna DJANGO_SETTINGS_MODULE, bo sie nie uda..."
    exit 1
fi

unamestr=`uname`

export DJANGO_SETTINGS_MODULE=django_bpp.settings.local

if [[ "$unamestr" == 'Linux' ]]; then
    export DISPLAY=localhost:1
    export DJANGO_SETTINGS_MODULE=django_bpp.settings.test
fi

pushd `dirname $0` > /dev/null
SCRIPTPATH=`pwd -P`
popd > /dev/null
cd $SCRIPTPATH/../src

NO_QUNIT=0
NO_PYTEST=0
NO_DJANGO=0
NO_REBUILD=0

export PYTHONIOENCODING=utf_8

while test $# -gt 0
do
    case "$1" in
        --no-qunit) NO_QUNIT=1
            ;;
        --no-pytest) NO_PYTEST=1
            ;;
        --no-django) NO_DJANGO=1
            ;;
        --no-rebuild) NO_REBUILD=1
            ;;
	--help) echo "--no-qunit, --no-pytest, --no-django, --no-rebuild"
	    exit 1
	    ;;
        --*) echo "bad option $1"
	    exit 1
            ;;
    esac
    shift
done

# LiveServer podejrzewam, że może potrzebować:
python manage.py collectstatic --noinput

if [ "$NO_QUNIT" == "0" ]; then
    ./node_modules/.bin/grunt qunit
fi

if [ "$NO_REBUILD" == "0" ]; then
    # Nie przebudowuj bazy danych przed uruchomieniem testów.
    # Baza powinna być zazwyczaj utworzona od zera. 
    dropdb test_bpp || true
    createdb test_bpp
    python manage.py create_test_db
    stellar replace test_bpp_v1 || stellar snapshot test_bpp_v1
fi

if [ "$NO_DJANGO" == "0" ]; then
    python manage.py test bpp --keepdb
    # Ewentualne następne testy muszą startować na czystej bazie danych
    stellar restore test_bpp_v1
fi

if [ "$NO_PYTEST" == "0" ]; then
    py.test functional_tests integrator2/tests eksport_pbn bpp/tests-pytest
    # mpasternak 17.1.2017 TODO: włączyć później
    # egeria/tests

    stellar restore test_bpp_v1
fi

