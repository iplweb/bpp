#!/bin/bash -e

unamestr=`uname`

export DJANGO_SETTINGS_MODULE=django_bpp.settings.local

if [[ "$unamestr" == 'Linux' ]]; then
    export DISPLAY=localhost:1
    export DJANGO_SETTINGS_MODULE=django_bpp.settings.test
fi

pushd `dirname $0` > /dev/null
SCRIPTPATH=`pwd -P`
popd > /dev/null
cd $SCRIPTPATH/..

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

export GIT_BRANCH_NAME=`git status |grep "On branch"|sed "s/On branch //"|sed "s/# //"`

if [ "$NO_REBUILD" == "0" ]; then
    # Nie przebudowuj bazy danych przed uruchomieniem testów.
    # Baza powinna być zazwyczaj utworzona od zera. 
    dropdb --if-exists test_bpp 
    createdb test_bpp
    python src/manage.py create_test_db
    stellar replace $GIT_BRANCH_NAME || stellar snapshot $GIT_BRANCH_NAME
else
    # --no-rebuild na command line, czyli baza danych została (prawdopodobnie) wcześniej
    # utworzona. Jednakże, dla zachowania integralności testów, chcemy pozbyć się 
    # ewentualnych artefaktów z testów, więc: 
    stellar restore $GIT_BRANCH_NAME
fi

if [ "$NO_DJANGO" == "0" ]; then
    python src/manage.py test bpp --keepdb
    # Ewentualne następne testy muszą startować na czystej bazie danych, więc:
    stellar restore $GIT_BRANCH_NAME
fi

if [ "$NO_PYTEST" == "0" ]; then

    # TravisCI debug BEGIN
    echo "Firefox version: "
    firefox -version || true
    echo "Geckodriver version: "
    geckodriver --version || true
    echo "Chromium version"
    chromium-browser --version || true
    echo "Chromedriver version: "
    chromedriver --version || true
    # TravisCI debug END

    py.test src/eksport_pbn tests src/integrator2/tests src/bpp/tests_pytest
    # mpasternak 17.1.2017 TODO: włączyć później
    # egeria/tests
    stellar restore $GIT_BRANCH_NAME
fi

if [ "$NO_QUNIT" == "0" ]; then
    grunt qunit
fi
