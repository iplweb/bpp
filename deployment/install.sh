#!/bin/bash -e

#
# Ten skrypt instaluje rzeczy potrzebne do budowania i do uruchamiania pakietu django-bpp
# po stronie systemu operacyjnego. 
#
# Zatem, dla Mac OS X używany będzie brew, dla Ubuntu - apt-get, i tak dalej. 
#
# Ten skrypt NIE może instalować nic za pomocą pip, nie instaluje nic do virtualenv, ten skrypt
# nie dotyka środowiska języka Python, lokalnego bądź globalnego, ten skrypt NIE dotyka go. Ten
# skrypt instaluje Pythona i potrzebne biblioteki. I bazę danych PostgreSQL. I jeszcze parę innych. 
#

platform='unknown'
unamestr=`uname`
hostnamestr=`hostname`

if [[ "$unamestr" == 'Linux' ]]; then

    # Niby nie powinniśmy się bawić w aktualizowanie systemu w tym miejscu ALE może się okazać, 
    # że pakietów nie da się w tym momencie pobrać, bo system maszyny wirtualnej np. ma stare linki
    # więc dla bezpieczeństwa lepiej odpalić o to, ale jeżeli np miałoby nie być sieci...
    sudo apt-get update || true

    sudo apt-get -y install python postgresql python-gevent python-psycopg2 python-imaging python-crypto python-simplejson python-sqlalchemy postgresql-plpython-9.3 postgresql-contrib-9.3 redis-server zip unzip
	
    if [[ "$hostnamestr" == "master" ]]; then
	
	# Install dev build packages
	sudo apt-get install -y  libpq-dev libjpeg-dev libpng-dev libxml2-dev libxslt1-dev libevent-dev firefox tightvncserver icewm libxslt1-dev python-dev npm

	sudo rm -f /usr/local/bin/node
	sudo ln -s /usr/bin/nodejs /usr/local/bin/node
	
    fi

elif [[ "$unamestr" == 'Darwin' ]]; then

	brew install python
	brew install node

	brew install postgresql --with-python
    ln -sfv /usr/local/opt/postgresql/*.plist ~/Library/LaunchAgents
    launchctl load ~/Library/LaunchAgents/homebrew.mxcl.postgresql.plist

	brew install redis
	ln -sfv /usr/local/opt/redis/*.plist ~/Library/LaunchAgents
    launchctl load ~/Library/LaunchAgents/homebrew.mxcl.redis.plist

	brew install rabbitmq
	ln -sfv /usr/local/opt/rabbitmq/*.plist ~/Library/LaunchAgents
    launchctl load ~/Library/LaunchAgents/homebrew.mxcl.rabbitmq.plist

    brew install nginx-full --with-push-stream-module
    ln -sfv /usr/local/opt/nginx-full/*.plist ~/Library/LaunchAgents
    launchctl load ~/Library/LaunchAgents/homebrew.mxcl.nginx-full.plist

fi

if [[ "$hostnamestr" == "master" ]] || [[ "$unamestr" == "Darwin" ]]; then
    npm config set proxy $HTTP_PROXY
    sudo npm config set proxy $HTTP_PROXY

    npm config set https-proxy $HTTPS_PROXY
    sudo npm config set https-proxy $HTTPS_PROXY

    sudo npm install -g grunt-cli bower

    yes n | bower
fi
