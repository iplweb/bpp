#!/bin/bash -e

# Buduje i instaluje wszystkie potrzebne pakiety w formacie wheel

. /home/vagrant/env/bin/activate

cd /vagrant/buildscripts/ && ./wheels.build.sh 
cd /vagrant/buildscripts/ && ./wheels.install.sh
cd /vagrant/requirements/ && pip --quiet install -r dev.requirements.txt
