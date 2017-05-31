#!/bin/bash -e

pushd `dirname $0` > /dev/null
SCRIPTPATH=`pwd -P`
popd > /dev/null
cd $SCRIPTPATH/..

export DISTDIR=$SCRIPTPATH/../dist
echo "Buduje wheels w $DISTDIR"

mkdir -p $DISTDIR
pip2 wheel --wheel-dir=$DISTDIR --find-links=$DISTDIR -r requirements.txt

export DISTDIR_DEV=${DISTDIR}_dev
mkdir -p $DISTDIR_DEV
pip2 wheel --wheel-dir=$DISTDIR_DEV --find-links=$DISTDIR --find-links=$DISTDIR_DEV -r requirements_dev.txt
