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

cd ../src/django_bpp

NO_QUNIT=0
NO_PYTEST=0
NO_DJANGO=0

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
	--help) echo "--no-qunit, --no-pytest, --no-django"
	    exit 1
	    ;;
        --*) echo "bad option $1"
	    exit 1
            ;;
    esac
    shift
done

if [ "$NO_QUNIT" == "0" ]; then
    grunt qunit
fi

if [ "$NO_PYTEST" == "0" ]; then
    py.test $PYTEST_OPTIONS functional_tests integrator2/tests eksport_pbn bpp/tests-pytest
fi

if [ "$NO_DJANGO" == "0" ]; then
    python manage.py test --noinput bpp -v 3
fi
