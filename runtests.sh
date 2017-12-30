#!/bin/bash -e

unamestr=`uname`

pushd `dirname $0` > /dev/null
SCRIPTPATH=`pwd -P`
popd > /dev/null

NO_REBUILD=0
PYTHON=python3.6

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-django_bpp.settings.local}"

export PYTHONIOENCODING=utf_8

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

if [ "$NO_REBUILD" == "0" ]; then
    # Nie przebudowuj bazy danych przed uruchomieniem testów.
    # Baza powinna być zazwyczaj utworzona od zera. 
    dropdb --if-exists test_bpp 
    createdb test_bpp
    $PYTHON src/manage.py create_test_db
    stellar replace $GIT_BRANCH_NAME || stellar snapshot $GIT_BRANCH_NAME
else
    # --no-rebuild na command line, czyli baza danych została (prawdopodobnie) wcześniej
    # utworzona. Jednakże, dla zachowania integralności testów, chcemy pozbyć się 
    # ewentualnych artefaktów z testów, więc: 
    stellar restore $GIT_BRANCH_NAME
fi

coverage run --source=src/bpp/ src/manage.py test bpp --keepdb
# Ewentualne następne testy muszą startować na czystej bazie danych, więc:
stellar restore $GIT_BRANCH_NAME

make clean-pycache

py.test --cov=src/eksport_pbn src/eksport_pbn/tests
py.test --cov=src/bpp src/integration_tests
py.test --cov=src/integrator2 src/integrator2/tests
py.test --cov=src/bpp src/bpp/tests_pytest
py.test --cov=src/nowe_raporty src/nowe_raporty/tests.py

# mpasternak 17.1.2017 TODO: włączyć później
# egeria/tests

stellar restore $GIT_BRANCH_NAME

coveralls
