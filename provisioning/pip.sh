#!/bin/bash

export WGET="wget --quiet -N -P /var/cache/wget" 

# PIP, Virtualenv
$WGET https://bootstrap.pypa.io/get-pip.py > /dev/null

sudo python /var/cache/wget/get-pip.py
sudo python3 /var/cache/wget/get-pip.py

sudo pip2 install virtualenv
sudo pip3 install virtualenv

rm /var/cache/wget/get-pip.py
