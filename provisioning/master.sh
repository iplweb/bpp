#!/bin/bash

# Basic APT stuff
apt-get install -y git mercurial build-essential python-dev python3-dev redis-server phantomjs postgresql pgtune postgresql-plpython tightvncserver
# firefox=28.0+build2-0ubuntu2

# PIP, Virtualenv
wget https://bootstrap.pypa.io/get-pip.py > /dev/null

sudo python get-pip.py
sudo python3 get-pip.py

sudo pip2 install virtualenv
sudo pip3 install virtualenv

# Git global config
git config --global user.email "michal.dtz@gmail.com"
git config --global user.name "Michał Pasternak"
git config --global push.default simple

# Ansible
sudo pip2 install ansible redis

# Hosts
echo "# Moje hosty: " >> /etc/hosts
echo "192.168.111.1 thinkpad thinkpad.localnet" >> /etc/hosts
echo "10.0.2.2 gate" >> /etc/hosts
echo "192.168.111.100 master master.localnet  messaging-test.localnet messaging-test" >> /etc/hosts
echo "192.168.111.101 staging" >> /etc/hosts
echo "192.168.111.150 selenium" >> /etc/hosts

# Hostname
echo "master" > /etc/hostname
hostname `cat /etc/hostname`

# User config
su vagrant -c "git config --global user.email michal.dtz@gmail.com"
su vagrant -c "git config --global user.name Michał\ Pasternak"
su vagrant -c "echo alias\ jed=emacs24-nox >> ~/.bashrc"
su vagrant -c "cd /home/vagrant && mkdir .gnupg && chmod 700 .gnupg"
su vagrant -c "git config --global push.default simple"

# Checkout ansible-playbook-bpp from GIT
# su vagrant -c "cd /home/vagrant && git clone git://192.168.111.1/ansible-bpp"
