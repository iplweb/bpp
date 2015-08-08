#!/bin/bash -e

platform='unknown'
unamestr=`uname`
hostnamestr=`hostname`

if [[ "$unamestr" == 'Linux' ]]; then

    sudo apt-get -y install python postgresql python-gevent python-psycopg2 python-imaging python-crypto python-simplejson python-sqlalchemy postgresql-plpython-9.3 postgresql-contrib-9.3 redis-server zip unzip
	
    if [[ "$hostnamestr" == "master" ]]; then
	
	# Install dev build packages
	sudo apt-get install -y  libpq-dev libjpeg-dev libpng-dev libxml2-dev libxslt1-dev libevent-dev firefox tightvncserver icewm libxslt1-dev python-dev npm

	sudo ln -s /usr/bin/nodejs /usr/local/bin/node
	
    fi

elif [[ "$unamestr" == 'Darwin' ]]; then

	brew install python
	brew install postgresql --with-python
	brew install redis
	brew install node

fi

if [[ "$hostnamestr" == "master" ]] || [[ "$unamestr" == "Darwin" ]]; then
    npm config set proxy $HTTP_PROXY
    sudo npm config set proxy $HTTP_PROXY

    npm config set https-proxy $HTTPS_PROXY
    sudo npm config set https-proxy $HTTPS_PROXY

    sudo npm install -g grunt-cli bower

    yes n | bower
fi
