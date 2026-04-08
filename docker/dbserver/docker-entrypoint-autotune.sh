#!/bin/bash

# Zainicjuj bazę danych standardowo (standardowo dla tego obrazu)
/usr/local/bin/docker-ensure-initdb.sh

# Jeżeli postgresql.conf nie zawiera linii "include_if_exists = /postgresql_optimized.conf" to dopisz ją
# na końcu pliku:
grep -qxF "include_if_exists = '/postgresql_optimized.conf'"  /var/lib/postgresql/data/postgresql.conf || echo "include_if_exists = '/postgresql_optimized.conf'" >> /var/lib/postgresql/data/postgresql.conf

# Wygeneruj /postgresql_optimized.conf
python /autotune.py > /postgresql_optimized.conf

# Na tym etapie NIE ma potrzeby restartu serwera PostgreSQL, ponieważ zatrzymała go procedura
# stop_tempserver z docker-ensure-initdb/docker-entrypoint. Zatem, wystartuj wszystko normalnie
# z parametrami takimi, jak przekazane:

exec /usr/local/bin/docker-entrypoint.sh "$@"
