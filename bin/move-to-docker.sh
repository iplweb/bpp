#!/bin/bash

# Skrypt ułatwiający przeniesienie bazy danych BPP z "metalowego" PostgreSQL
# na PostgreSQL w dockerze + deinstalujący pakiety z "metalowego" serwera
# które nie będą potrzebne po dockeryzacji:

# Uruchamiac na "metalowym" serwerze.

# Nazwa bazy danych na "metalowym" serwerze
DB_NAME=bpp

# ID kontenera z bazą danych
DB_CONTAINER=` docker ps | grep dbserver| cut -d\  -f1`

# ID kontenera z webserverem
WEB_CONTAINER=` docker ps | grep webserver| cut -d\  -f1`

# Zatrzymaj usługi "metalowe"
supervisorctl stop all

# Zatrzymaj webserver dockera
docker container pause $WEB_CONTAINER

# Skasuj i utwórz pustą bazę BPP po stronie dockera
docker exec -it $DB_CONTAINER dropdb --force -U postgres bpp
docker exec -it $DB_CONTAINER createdb -U postgres bpp
docker exec -it $DB_CONTAINER createuser -U postgres -s bpp

# Wczytaj dump bazy do PostgreSQLa
pg_dump $DB_NAME | docker exec -t $DB_CONTAINER psql bpp

# Odpauzuj web container
docker container unpause $WEB_CONTAINER

# Zatrzymaj "metalowego" PostgreSQL
service postgresql stop
apt remove postgresql-14 redis nginx supervisor
apt autoremove
apt clean
apt autoclean
