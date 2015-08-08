#!/bin/sh -e

if [ -z "$VIRTUAL_ENV" ]; then
    echo "Ten skrypt dziala spod virtualenv, aktywuj jakies"
    exit 1
fi

export DISTDIR=${1-./DIST/}

echo "Instaluje wheels z $DISTDIR"

export PIP_WHEEL="pip install --find-links=$DISTDIR --use-wheel -v"

platform='unknown'
unamestr=`uname`

if [[ "$unamestr" == 'Linux' ]]; then
    $PIP_WHEEL -r requirements/ubuntu.requirements.txt

elif [[ "$unamestr" == 'Darwin' ]]; then
    $PIP_WHEEL lxml
    $PIP_WHEEL -r requirements/osx.requirements.txt

fi

$PIP_WHEEL -r requirements/requirements.txt

