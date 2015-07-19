#!/bin/bash

# Extra swap - 2 GB
dd if=/dev/zero of=/swapfile bs=1M count=2048
mkswap /swapfile
swapon /swapfile

echo swapon /swapfile > /etc/rc.local
echo exit 0 >> /etc/rc.local

# Basic APT stuff
apt-get update -qq
apt-get dist-upgrade -y
apt-get install -y git mercurial build-essential mc emacs24-nox yaml-mode python-dev python3-dev sshpass links redis-server jed lxde xinit wpolish dictionaries-common

# firefox=28.0+build2-0ubuntu2

# PIP, Virtualenv
wget https://bootstrap.pypa.io/get-pip.py

sudo python get-pip.py
sudo python3 get-pip.py

sudo pip2 install virtualenv
sudo pip3 install virtualenv

# Git global config
git config --global user.email "michal.dtz@gmail.com"
git config --global user.name "Michał Pasternak"
git config --global core.autocrlf true

# Ansible
sudo pip2 install ansible redis

# Hosts
echo "# Moje hosty: " >> /etc/hosts
echo "192.168.111.1 thinkpad thinkpad.localnet" >> /etc/hosts
echo "10.0.2.2 gate" >> /etc/hosts
echo "192.168.111.100 master master.localnet  messaging-test.localnet messaging-test" >> /etc/hosts
echo "192.168.111.101 staging" >> /etc/hosts

# Hostname
echo "master" > /etc/hostname
hostname `cat /etc/hostname`


# User config
su vagrant -c "git config --global user.email michal.dtz@gmail.com"
su vagrant -c "git config --global user.name Michał\ Pasternak"
su vagrant -c "git config --global core.autocrlf true"
su vagrant -c "echo alias\ jed=emacs24-nox >> ~/.bashrc"
su vagrant -c "mkdir -p ~/.cache/pip && cd ~/.cache/pip && ln -s /pip-cache-http http && ln -s /pip-cache-wheels wheels"
su vagrant -c "cd /home/vagrant && mkdir Desktop"
su vagrant -c "cd /home/vagrant && mkdir .gpg && chmod 700 .gpg"

# Checkout ansible-playbook-bpp from GIT
su vagrant -c "cd /home/vagrant && git clone git://192.168.111.1/ansible-bpp"

# Autologin
cd /etc/lxdm
cat lxdm.conf | sed -e "s/# autologin=dgod/autologin=vagrant/g" > lxdm-new.conf
cp lxdm.conf lxdm.conf.bak
mv lxdm-new.conf lxdm.conf

