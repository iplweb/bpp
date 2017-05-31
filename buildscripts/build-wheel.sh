#!/bin/bash -e

pushd `dirname $0` > /dev/null
SCRIPTPATH=`pwd -P`
popd > /dev/null
cd $SCRIPTPATH/..

export DISTDIR=$SCRIPTPATH/../dist
echo "Buduje wheels w $DISTDIR"

mkdir -p $DISTDIR
pip2 wheel --wheel-dir=$DISTDIR --find-links=$DISTDIR -r requirements.txt
python setup.py bdist_wheel
