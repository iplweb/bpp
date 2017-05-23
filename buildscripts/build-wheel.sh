#!/bin/bash -e

pushd `dirname $0` > /dev/null
SCRIPTPATH=`pwd -P`
popd > /dev/null
cd $SCRIPTPATH/..

export DISTDIR=$SCRIPTPATH/../DIST
echo "Buduje wheels w $DISTDIR"

mkdir -p $DISTDIR
pip wheel --wheel-dir=$DISTDIR --find-links=$DISTDIR $SCRIPTPATH/..
