#!/bin/bash

# Basic APT stuff
apt-get install -y git

# Git global config
git config --global user.email "michal.dtz@gmail.com"
git config --global user.name "Michał Pasternak"
git config --global push.default simple

# User config
su vagrant -c "git config --global user.email michal.dtz@gmail.com"
su vagrant -c "git config --global user.name Michał\ Pasternak"
su vagrant -c "git config --global push.default simple"
