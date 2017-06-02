#!/bin/bash

export HOSTNAME=`hostname`
export THIS_CONTAINER_IP=`cat /etc/hosts |grep $HOSTNAME|cut  -f 1`
export DJANGO_LIVE_TEST_SERVER_ADDRESS=$THIS_CONTAINER_IP:9015

export DISPLAY=:99

Xvfb $DISPLAY &

bash $*
