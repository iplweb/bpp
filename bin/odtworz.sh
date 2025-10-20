#!/bin/bash
set -euo pipefail

# Ten skrypt:
# 1) ubija proces runserver
# 2) archiwizuje istniejącą bazę danych bpp (używając stash_db.sh)
# 3) instaluje baze danych z bpp z backupu (pierwszy parametr)
# 4) tworzy konto superuzytkownika 'admin' z haslem 'foobar123'
#
# 5?... moglby kiedys uruchamiac runserver

BASEDIR=$(dirname "$0")

# Sprawdź czy podano parametr z plikiem pg_dump
if [ $# -eq 0 ]; then
    echo "Błąd: Wymagana jest ścieżka do pliku pg_dump"
    echo "Użycie: $0 <ścieżka_do_pliku_pg_dump>"
    echo ""
    echo "Ten skrypt odtwarza bazę danych BPP z backupu."
    exit 1
fi

LOCAL_DATABASE_NAME=bpp

# Opcjonalnie: możnaby tu ubić serwer Django, ale ponieważ jest dropdb -f,
# to nie ma takiej potrzeby. Ewentualnie możnaby go zrestartować po wszystkim, wysyłając
# sygnał, ale Django chyba na ten moment nie obsługuje czegoś takiego...
# https://stackoverflow.com/questions/79652902/can-the-django-development-server-be-restarted-with-a-signal
#
# pkill -TERM -f "src/manage.py runserver" || true
# sleep 1

# Stash the existing database if it exists (instead of dropping it)
if psql -lqt | cut -d \| -f 1 | grep -qw "$LOCAL_DATABASE_NAME"; then
    "$BASEDIR/stash_db.sh"
fi

createdb $LOCAL_DATABASE_NAME
createuser -s mimooh || true
createuser -s bpp || true

pg_restore -j 6 -d $LOCAL_DATABASE_NAME  "$1" || true

for tbl in `psql -qAt -c "select tablename from pg_tables where schemaname = 'public';" $LOCAL_DATABASE_NAME` ; do  psql -c "alter table \"$tbl\" owner to postgres" $LOCAL_DATABASE_NAME ; done

for tbl in `psql -qAt -c "select sequence_name from information_schema.sequences where sequence_schema = 'public';" $LOCAL_DATABASE_NAME` ; do  psql -c "alter sequence \"$tbl\" owner to postgres" $LOCAL_DATABASE_NAME ; done

cd "$BASEDIR/.."
python src/manage.py migrate

# Update django_site domain to localhost for development
psql $LOCAL_DATABASE_NAME -c "UPDATE django_site SET domain='127.0.0.1:8000' WHERE id=1;" || true

python src/manage.py createsuperuser --noinput --username admin --email michal.dtz@gmail.com || true
./bin/ustaw-domyslne-haslo-admina.sh
