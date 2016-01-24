#!/bin/bash -e

CONFIG_PATH="/etc/postgresql/9.3/main"

echo "host all all 192.168.111.0/24 trust" >> $CONFIG_PATH/pg_hba.conf
echo "listen_addresses='*'" >> $CONFIG_PATH/postgresql.conf

pgtune  -i $CONFIG_PATH/postgresql.conf > $CONFIG_PATH/optimized.postgresql.conf
mv $CONFIG_PATH/postgresql.conf $CONFIG_PATH/postgresql.conf.orig
cp $CONFIG_PATH/optimized.postgresql.conf $CONFIG_PATH/postgresql.conf

service postgresql restart

