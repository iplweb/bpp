#!/bin/bash -e

# Ten skrypt:
# 1) ubija proces runserver
# 2) usuwa baze dancyh bpp
# 3) instaluje baze danych z bpp z backupu (pierwszy parametr)
# 4) tworzy konto superuzytkownika 'admin' z haslem 'foobar123'
#
# 5?... moglby kiedys uruchamiac runserver

BASEDIR=$(dirname "$0")

pkill -TERM -f "src/manage.py runserver" || true

sleep 1

dropdb --if-exists bpp

pg_restore -j 6 -d template1  -C "$1" || true

for tbl in `psql -qAt -c "select tablename from pg_tables where schemaname = 'public';" bpp` ; do  psql -c "alter table \"$tbl\" owner to postgres" bpp ; done

for tbl in `psql -qAt -c "select sequence_name from information_schema.sequences where sequence_schema = 'public';" bpp` ; do  psql -c "alter sequence \"$tbl\" owner to postgres" bpp ; done

cd "$BASEDIR/.."
python src/manage.py migrate
python src/manage.py createsuperuser --noinput --username admin --email michal.dtz@gmail.com || true
./bin/ustaw-domyslne-haslo-admina.sh
