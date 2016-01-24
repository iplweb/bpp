#!/bin/bash -e

#
# Ten skrypt buduje pakiety WHL z których korzysta django-bpp
#

if [ -z "$VIRTUAL_ENV" ]; then
    echo "Ten skrypt dziala spod virtualenv, aktywuj jakies"
    exit 1
fi

export DISTDIR=${1-./DIST/}

echo "Buduje wheels w $DISTDIR"

mkdir -p $DISTDIR

export PIP_WHEEL="pip --quiet wheel --wheel-dir=$DISTDIR --find-links=$DISTDIR --use-wheel -v"

platform='unknown'
unamestr=`uname`

if [[ "$unamestr" == 'Linux' ]]; then
    $PIP_WHEEL -r ../requirements/$unamestr.requirements.txt

elif [[ "$unamestr" == 'Darwin' ]]; then

    # http://louistiao.me/posts/installing-lxml-on-mac-osx-1011-inside-a-virtualenv-with-pip.html
    # $ STATIC_DEPS=true LIBXML2_VERSION=2.9.2 pip install lxml
    for f in $DISTDIR/lxml*macosx*; do
	[ -e "$f" ] && echo "lxml exists, not building" || $PIP_WHEEL --build-option="--static-deps" --build-option="--libxml2-version=2.9.2" lxml 
	break
    done

    $PIP_WHEEL -r ../requirements/$unamestr.requirements.txt
fi

$PIP_WHEEL -r ../requirements/src.requirements.txt
$PIP_WHEEL -r ../requirements/dev.requirements.txt
