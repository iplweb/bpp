#!/bin/bash -e


pushd `dirname $0` > /dev/null
SCRIPTPATH=`pwd -P`
popd > /dev/null

cd $SCRIPTPATH/..

grunt build
python src/manage.py collectstatic --noinput
python src/manage.py compress --force
