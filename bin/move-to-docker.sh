#!/bin/bash

# Skrypt ułatwiający przeniesienie bazy danych BPP z "metalowego" PostgreSQL
# na PostgreSQL w dockerze + deinstalujący pakiety z "metalowego" serwera
# które nie będą potrzebne po dockeryzacji:

# NIE uruchamiac, traktować jako luźną propozycję wyciągnięcia informacji z metalowego
# serwera...



# Skopiuj ustawienia z plików ~/.env, ~/.env.local, ~/env/bin/activate
# do pliku .env obok docker-compose
cat .env .env.local env/bin/activate > .env

# uważaj na znak dolara w pliku .env (docker sprobuje substytuowac)
# uważaj na "localhost" w pliku .env
# ustaw DJANGO_BPP_REDIS_SERVER="redis"


# Skonfiguruj wykonywanie kopii zapasowej
cd /home/backup-ipl/...
cp rclone-config ...

# Zatrzymaj nginx
service nginx stop

# Nazwa bazy danych na "metalowym" serwerze
DB_NAME=bpp

# ID kontenera z bazą danych
DB_CONTAINER=` docker ps | grep dbserver| cut -d\  -f1`

# ID kontenera z webserverem
WEB_CONTAINER=` docker ps | grep webserver| cut -d\  -f1`

# ID kontenera z aplikacją
APP_CONTAINER=` docker ps | grep appserver-1 | cut -d\  -f1`

# Zatrzymaj usługi "metalowe"
supervisorctl stop all

# Skasuj i utwórz pustą bazę BPP po stronie dockera
docker exec -it $DB_CONTAINER dropdb --force -U postgres bpp
docker exec -it $DB_CONTAINER createdb -U postgres bpp
docker exec -it $DB_CONTAINER createuser -U postgres -s bpp

# Wczytaj dump bazy do PostgreSQLa
pg_dump $DB_NAME | docker exec -i $DB_CONTAINER psql -U postgres bpp

# Zatrzymaj "metalowego" PostgreSQL
service postgresql stop
# apt remove postgresql-14
systemctl disable postgresql

apt remove -y redis-server redis supervisor nginx-*
apt autoremove -y
apt clean
apt autoclean

# Usuń crontaby
sudo crontab -e
su - bpp -c "crontab -e"

# Skopiuj mediaroot
cd ~bpp/media/  && docker cp . $APP_CONTAINER:/mediaroot

# Usuń użytkownika systemowego "bpp"
userdel bpp
