#!/bin/bash -e

if [ -z "$VIRTUAL_ENV" ]; then
    echo "Ten skrypt dziala spod virtualenv, aktywuj jakies"
    exit 1
fi

export DISTDIR=${1-./DIST/}

echo "Instaluje wheels z $DISTDIR"

export PIP_INSTALL="pip install --find-links=$DISTDIR --use-wheel -v"

unamestr=`uname`
hostnamestr=`hostname`

if [[ "$unamestr" == 'Linux' ]]; then
    $PIP_INSTALL -r requirements/Linux.requirements.txt

elif [[ "$unamestr" == 'Darwin' ]]; then
    $PIP_INSTALL lxml
    $PIP_INSTALL -r requirements/Darwin.requirements.txt

fi

$PIP_INSTALL -r requirements/requirements.txt

if [[ "$hostnamestr" == "Macbook-Pro-Michala.local" ]]; then
    $PIP_INSTALL -r requirements/dev.requirements.txt
fi

if [[ "$hostnamestr" == "master" ]]; then
    $PIP_INSTALL -r requirements/dev.requirements.txt
fi
