#!/bin/bash -e


pushd `dirname $0` > /dev/null
SCRIPTPATH=`pwd -P`
popd > /dev/null

cd $SCRIPTPATH/..

grunt build > /dev/null
python src/manage.py collectstatic --noinput -v0
python src/manage.py compress --force -v0
