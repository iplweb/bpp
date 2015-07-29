#!/usr/bin/env bash

cd /home/vagrant && chmod 600 .gnupg/* && chmod 700 .gnupg/


echo "listen_addresses = '*'" >> /etc/postgresql/9.3/main/postgresql.conf
echo "192.168.111.100 master master.localnet" >> /etc/postgresql/9.3/main/pg_hba.conf

apt-get install -y pgtune

pgtune -i /etc/postgresql/9.3/main/postgresql.conf -o /etc/postgresql/9.3/main/postgresql.conf.new
mv /etc/postgresql/9.3/main/postgresql.conf /etc/postgresql/9.3/main/postgresql.conf.ORIG
mv /etc/postgresql/9.3/main/postgresql.conf.new /etc/postgresql/9.3/main/postgresql.conf

service postgresql restart

cat /etc/redis/redis.conf | sed -e "s/bind 127.0.0.1/\# bind 127.0.0.1/g" > /etc/redis/redis.conf.new
mv /etc/redis/redis.conf /etc/redis/redis.conf.ORIG
mv /etc/redis/redis.conf.new /etc/redis/redis.conf

service redis-server restart