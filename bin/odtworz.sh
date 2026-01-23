#!/bin/bash
set -euo pipefail

# Ten skrypt:
# 1) usuwa istniejącą bazę danych bpp
# 2) instaluje baze danych z bpp z backupu (pierwszy parametr)
# 3) tworzy konto superuzytkownika 'admin' z haslem 'foobar123'

BASEDIR=$(dirname "$0")

# Default values
NO_OWNER=true
DUMP_FILE=""

# Parse command line options
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--no-owner)
            NO_OWNER=true
            shift
            ;;
        -o|--with-owner)
            NO_OWNER=false
            shift
            ;;
        -h|--help)
            echo "Użycie: $0 [-o|--with-owner] <ścieżka_do_pliku_pg_dump>"
            echo ""
            echo "Ten skrypt odtwarza bazę danych BPP z backupu."
            echo ""
            echo "Opcje:"
            echo "  -o, --with-owner  Przywróć właścicieli obiektów z dumpu"
            echo "                    (domyślnie: pomijaj właścicieli)"
            echo "  -n, --no-owner    [przestarzałe] Nie przywracaj właścicieli"
            echo "                    (to jest teraz domyślne zachowanie)"
            echo "  -h, --help        Wyświetl tę pomoc"
            exit 0
            ;;
        -*)
            echo "Nieznana opcja: $1"
            echo "Użycie: $0 [-o|--with-owner] <ścieżka_do_pliku_pg_dump>"
            exit 1
            ;;
        *)
            DUMP_FILE="$1"
            shift
            ;;
    esac
done

# Sprawdź czy podano parametr z plikiem pg_dump
if [ -z "$DUMP_FILE" ]; then
    echo "Błąd: Wymagana jest ścieżka do pliku pg_dump"
    echo "Użycie: $0 [-o|--with-owner] <ścieżka_do_pliku_pg_dump>"
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

# Drop the database if it exists
dropdb -f "$LOCAL_DATABASE_NAME" 2>/dev/null || true

createdb $LOCAL_DATABASE_NAME

# Filter out harmless errors from pg_restore (e.g., unknown config parameters
# from newer PostgreSQL versions)
filter_pg_restore_errors() {
    grep -v "transaction_timeout" >&2
}

if [ "$NO_OWNER" = true ]; then
    pg_restore -j 6 --no-owner -d $LOCAL_DATABASE_NAME "$DUMP_FILE" \
        2> >(filter_pg_restore_errors) || true
else
    pg_restore -j 6 -d $LOCAL_DATABASE_NAME "$DUMP_FILE" \
        2> >(filter_pg_restore_errors) || true
fi

# Clear denorm dirty instances to avoid unnecessary recalculations after restore
psql $LOCAL_DATABASE_NAME -c "DELETE FROM denorm_dirtyinstance;" || true

#for tbl in `psql -qAt -c "select tablename from pg_tables where schemaname = 'public';" $LOCAL_DATABASE_NAME` ; do  psql -c "alter table \"$tbl\" owner to postgres" $LOCAL_DATABASE_NAME ; done
# for tbl in `psql -qAt -c "select sequence_name from information_schema.sequences where sequence_schema = 'public';" $LOCAL_DATABASE_NAME` ; do  psql -c "alter sequence \"$tbl\" owner to postgres" $LOCAL_DATABASE_NAME ; done

cd "$BASEDIR/.."
make migrate

# Update django_site domain to localhost for development
psql $LOCAL_DATABASE_NAME -c "UPDATE django_site SET domain='127.0.0.1:8000' WHERE id=1;" || true

uv run src/manage.py createsuperuser --noinput --username admin --email michal.dtz@gmail.com || true
./bin/ustaw-domyslne-haslo-admina.sh

make invalidate
