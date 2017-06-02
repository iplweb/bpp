#!/bin/bash -e

pip2 install --no-index --find-links=./dist_dev --find-links=./dist -rrequirements_dev.txt

./buildscripts/build-assets.sh

