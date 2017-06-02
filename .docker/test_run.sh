#!/bin/bash -e

pip2 install --no-index --find-links=./dist_dev --find-links=./dist -rrequirements_dev.txt

export DISPLAY=:50
export PGUSER=postgres
export PGHOST=db

Xvfb $DISPLAY &

./buildscripts/build-assets.sh

tox --notest