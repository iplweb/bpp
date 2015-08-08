#!/bin/sh -e

platform='unknown'
unamestr=`uname`

hostnamestr=`

if [[ "$unamestr" == 'Linux' ]]; then

	apt-get -y install python postgresql python-gevent python-psycopg2 python-imaging python-crypto python-simplejson python-sqlalchemy postgresql-plpython-9.3 postgresql-contrib-9.3 redis-server zip unzip
	
	if [[ "$hostnamestr" == "master" ]]; then
	
		# Install dev build packages
		sudo apt-get install -y  libpq-dev libjpeg-dev libpng-dev libxml2-dev libxslt1-dev libevent-dev firefox tightvncserver icewm libxslt1-dev python-dev
	
	fi

elif [[ "$unamestr" == 'Darwin' ]]; then

	brew install python
	brew install postgresql --with-python
	brew install redis

fi
