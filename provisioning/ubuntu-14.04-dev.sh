#!/bin/bash -e

#
# Ten skrypt instaluje rzeczy potrzebne do budowania i do uruchamiania pakietu django-bpp
# po stronie systemu operacyjnego Ubuntu 14.04
#
# Ten skrypt NIE może instalować nic za pomocą pip, nie instaluje nic do virtualenv, ten skrypt
# nie dotyka środowiska języka Python, lokalnego bądź globalnego, ten skrypt NIE dotyka go. Ten
# skrypt instaluje Pythona i potrzebne biblioteki. 
#
# PostgreSQL jest na oddzielnym hoscie.

# Install dev build packages
sudo apt-get -qq install -y libpq-dev libjpeg-dev libpng-dev libxml2-dev libxslt1-dev libevent-dev libxslt1-dev python-dev npm

sudo rm -f /usr/local/bin/node
sudo ln -s /usr/bin/nodejs /usr/local/bin/node

sudo npm install --quiet -g grunt-cli bower

yes n | sudo -i -u vagrant bower > /dev/null