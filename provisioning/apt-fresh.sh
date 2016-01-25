#!/bin/bash

apt-get -qq update 
apt-get -qq dist-upgrade -y
apt-get -qq autoremove -y
