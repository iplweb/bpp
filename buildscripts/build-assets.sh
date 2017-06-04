#!/bin/bash -e


pushd `dirname $0` > /dev/null
SCRIPTPATH=`pwd -P`
popd > /dev/null

cd $SCRIPTPATH/..

yarn install > /dev/null

python src/manage.py bower_install -RF -v0

npm rebuild > /dev/null

rm -rf src/django_bpp/staticroot
python src/manage.py collectstatic --noinput -v0

grunt build 

python src/manage.py collectstatic --noinput -v0

python src/manage.py compress --force  -v0
echo -n "Static root size: "
du -ch src/django_bpp/staticroot | grep total