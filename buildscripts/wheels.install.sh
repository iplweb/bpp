#!/bin/bash -e

#
# Ten skrypt instaluje pakiety WHL, z których krozysta django-bpp
#

if [ -z "$VIRTUAL_ENV" ]; then
    echo "Ten skrypt dziala spod virtualenv, aktywuj jakies"
    exit 1
fi

export DISTDIR=${1-./DIST/}

echo "Instaluje wheels z $DISTDIR"

export PIP_INSTALL="pip --quiet install --find-links=$DISTDIR --use-wheel -v"

unamestr=`uname`
hostnamestr=`hostname`

if [[ "$unamestr" == 'Darwin' ]]; then
    $PIP_INSTALL lxml
fi

$PIP_INSTALL -r ../requirements/$unamestr.requirements.txt
$PIP_INSTALL -r ../requirements/requirements.txt

if [[ "$unamestr" == 'Darwin' ]]; then
    $PIP_INSTALL -r ../requirements/dev.requirements.txt
fi
