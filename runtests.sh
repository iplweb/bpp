#!/bin/bash -e

unamestr=`uname`

pushd `dirname $0` > /dev/null
SCRIPTPATH=`pwd -P`
popd > /dev/null

DEBUG=0
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
	--debug) DEBUG=1
	    ;;
	--help) echo "--no-qunit, --no-pytest, --no-django, --no-rebuild, --debug"
	    exit 1
	    ;;
        --*) echo "bad option $1"
	    exit 1
            ;;
    esac
    shift
done

# export GIT_BRANCH_NAME=`git status |grep "On branch"|sed "s/On branch //"|sed "s/# //"`

if [ "$DEBUG" == "1" ]; then
    echo "------------------------------------------------------------------------------"
    echo -n "Firefox version: "
    firefox -version || true
    echo -n "Geckodriver version: "
    geckodriver --version || true 
    echo -n "Chromium version"
    chromium-browser --version || true
    echo -n "Chromedriver version: "
    chromedriver --version || true
    #echo "------------------------------------------------------------------------------"
    #echo -n "Git version: "
    #git --version
    #echo "Git status: " 
    #git status
    #echo "------------------------------------------------------------------------------"
    #echo -n "Git branch detected: "
    #echo $GIT_BRANCH_NAME
    echo "------------------------------------------------------------------------------"
    echo -n "DJANGO_LIVE_TEST_SERVER_ADDRESS: "
    echo $DJANGO_LIVE_TEST_SERVER_ADDRESS 
    echo "------------------------------------------------------------------------------"
    echo "pytest.ini: "
    echo "------------------------------------------------------------------------------"
    cat pytest.ini
    echo "------------------------------------------------------------------------------"
    echo "tox.ini"
    echo "------------------------------------------------------------------------------"
    cat tox.ini
fi

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
    coverage run --source='src/bpp/' src/manage.py test bpp --keepdb
    # Ewentualne następne testy muszą startować na czystej bazie danych, więc:
    stellar restore $GIT_BRANCH_NAME
fi

if [ "$NO_PYTEST" == "0" ]; then
    py.test --cov=eksport_pbn src/eksport_pbn
    py.test --cov=bpp src/integration_tests
    py.test --cov=integrator2 src/integrator2/tests
    py.test --cov=bpp src/bpp/tests_pytest
    py.test --cov=nowe_raporty src/nowe_raporty/tests.py

    # mpasternak 17.1.2017 TODO: włączyć później
    # egeria/tests

    stellar restore $GIT_BRANCH_NAME
fi

if [ "$NO_QUNIT" == "0" ]; then
    npm rebuild
    grunt qunit -v
fi
