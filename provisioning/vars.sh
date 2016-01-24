#!/bin/bash -e

echo "export DJANGO_SETTINGS_MODULE=django_bpp.settings.test" >> ~/.bashrc
echo "export DJANGO_BPP_SECRET_KEY=0xdeadbeef" >> ~/.bashrc

echo "export PGHOST=bpp-db" >> ~/.bashrc
echo "export PGUSER=bpp" >> ~/.bashrc
echo "export PGPASSWORD=password" >> ~/.bashrc
echo "export PGDATABASE=bpp" >> ~/.bashrc

echo ". /home/vagrant/env/bin/activate" >> ~/.bashrc

