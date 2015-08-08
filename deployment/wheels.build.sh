#!/bin/bash -e

if [ -z "$VIRTUAL_ENV" ]; then
    echo "Ten skrypt dziala spod virtualenv, aktywuj jakies"
    exit 1
fi

export DISTDIR=${1-./DIST/}

echo "Buduje wheels w $DISTDIR"

mkdir -p $DISTDIR

export PIP_WHEEL="pip wheel --wheel-dir=$DISTDIR --find-links=$DISTDIR --use-wheel -v"

platform='unknown'
unamestr=`uname`

if [[ "$unamestr" == 'Linux' ]]; then
    $PIP_WHEEL -r requirements/$unamestr.requirements.txt

elif [[ "$unamestr" == 'Darwin' ]]; then


    for f in $DISTDIR/lxml*macosx*; do
	[ -e "$f" ] && echo "lxml exists, not building" || $PIP_WHEEL --build-option="--static-deps" lxml 
	break
    done

    $PIP_WHEEL -r requirements/$unamestr.requirements.txt

fi

$PIP_WHEEL -r requirements/src.requirements.txt
$PIP_WHEEL -r requirements/requirements.txt
$PIP_WHEEL -r requirements/dev.requirements.txt
