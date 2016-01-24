#!/bin/bash -e

#
# Ten skrypt instaluje rzeczy potrzebne do budowania i do uruchamiania pakietu django-bpp
# po stronie systemu operacyjnego Mac OS X
#
# Zatem, dla Mac OS X używany będzie brew, dla Ubuntu - apt-get, i tak dalej. 
#
# Ten skrypt NIE może instalować nic za pomocą pip, nie instaluje nic do virtualenv, ten skrypt
# nie dotyka środowiska języka Python, lokalnego bądź globalnego, ten skrypt NIE dotyka go. Ten
# skrypt instaluje Pythona i potrzebne biblioteki. I bazę danych PostgreSQL. I jeszcze parę innych. 
#

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

sudo npm install -g grunt-cli bower

yes n | bower
