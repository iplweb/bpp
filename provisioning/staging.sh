#!/usr/bin/env bash

apt-get update -qq
apt-get dist-upgrade -y
apt-get install -y sshpass jed emacs24-nox

# Hosts
echo "# Moje hosty: " >> /etc/hosts
echo "192.168.111.1 thinkpad thinkpad.localnet" >> /etc/hosts
echo "10.0.2.2 gate" >> /etc/hosts
echo "192.168.111.100 master master.localnet  messaging-test.localnet messaging-test" >> /etc/hosts
echo "192.168.111.101 staging staging-bpp.local" >> /etc/hosts
echo "192.168.111.150 selenium" >> /etc/hosts

echo "staging" > /etc/hostname
hostname `cat /etc/hostname`
