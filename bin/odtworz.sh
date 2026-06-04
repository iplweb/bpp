#!/bin/bash
set -euo pipefail

# Ten skrypt:
# 1) usuwa istniejącą bazę danych bpp
# 2) instaluje baze danych z bpp z backupu (pierwszy parametr)
# 3) tworzy konto superuzytkownika 'admin' z haslem 'foobar123'
#
# Obsługiwane formaty backupu (autodetekcja po ZAWARTOŚCI, nie po nazwie):
#   - pg_dump -Fc  (custom, pojedynczy plik)
#   - pg_dump -Ft  (tar)
#   - pg_dump -Fd  (katalog) — także spakowany jako .tar.gz / .tgz
#   - dowolny z powyższych dodatkowo skompresowany gzipem (.gz)

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
            echo "Format backupu wykrywany jest po zawartości pliku:"
            echo "  pg_dump -Fc/-Ft/-Fd, także spakowane .gz / .tar.gz / .tgz"
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

# Katalog tymczasowy na rozpakowane archiwa; sprzątany przy wyjściu (też
# przy błędzie, dzięki trap EXIT).
WORKDIR=""
cleanup() {
    [ -n "${WORKDIR:-}" ] && rm -rf "$WORKDIR"
    return 0
}
trap cleanup EXIT

# Ustala, co faktycznie podać pg_restore. Wynik ląduje w DUMP_TARGET.
# Autodetekcja po zawartości pliku (nie po rozszerzeniu):
#   - format wprost czytelny dla pg_restore (-Fc / -Ft / katalog -Fd) → bez zmian,
#   - .tar.gz / .tgz owijający katalogowy dump (pg_dump -Fd) → rozpakowanie,
#   - pojedynczy dump skompresowany gzipem (np. pg_dump -Fc | gzip) → dekompresja.
# Rozpakowane dane trafiają do $WORKDIR i są kasowane przez trap.
DUMP_TARGET=""
resolve_dump_target() {
    local f="$1"

    if [ ! -e "$f" ]; then
        echo "Błąd: plik backupu nie istnieje: $f" >&2
        exit 1
    fi

    # Format, który pg_restore czyta bezpośrednio: custom (-Fc), tar (-Ft)
    # albo rozpakowany katalog (-Fd). pg_restore -l czyta tylko spis treści.
    if pg_restore -l "$f" >/dev/null 2>&1; then
        DUMP_TARGET="$f"
        return
    fi

    # Nie jest to bezpośredni dump — spróbuj rozpakować gzip.
    if gzip -t "$f" >/dev/null 2>&1; then
        WORKDIR="$(mktemp -d)"
        if gzip -dc "$f" | tar -tf - >/dev/null 2>&1; then
            # .tar.gz owijający katalogowy dump (pg_dump -Fd): toc.dat + *.dat.gz
            echo "Rozpakowuję archiwum katalogowe (pg_dump -Fd)..."
            gzip -dc "$f" | tar -xf - -C "$WORKDIR"
            local toc
            toc="$(find "$WORKDIR" -maxdepth 3 -name toc.dat -print -quit)"
            if [ -z "$toc" ]; then
                echo "Błąd: w archiwum nie znaleziono dumpu pg_dump (brak toc.dat)." >&2
                exit 1
            fi
            DUMP_TARGET="$(dirname "$toc")"
            return
        fi
        # Pojedynczy dump skompresowany gzipem (np. pg_dump -Fc | gzip).
        echo "Rozpakowuję skompresowany dump (gzip)..."
        gzip -dc "$f" > "$WORKDIR/dump"
        DUMP_TARGET="$WORKDIR/dump"
        return
    fi

    echo "Błąd: nieobsługiwany format pliku backupu: $f" >&2
    echo "Obsługiwane: pg_dump -Fc/-Ft/-Fd oraz ich warianty .gz / .tar.gz" >&2
    exit 1
}

# Walidujemy i ewentualnie rozpakowujemy backup ZANIM cokolwiek zburzymy
# (docker compose down -v / DROP DATABASE). Dzięki temu zły plik wywala się
# od razu, bez ruszania bieżącej bazy.
resolve_dump_target "$DUMP_FILE"

# Opcjonalnie: możnaby tu ubić serwer Django, ale ponieważ jest dropdb -f,
# to nie ma takiej potrzeby. Ewentualnie możnaby go zrestartować po wszystkim, wysyłając
# sygnał, ale Django chyba na ten moment nie obsługuje czegoś takiego...
# https://stackoverflow.com/questions/79652902/can-the-django-development-server-be-restarted-with-a-signal
#
# pkill -TERM -f "src/manage.py runserver" || true
# sleep 1

# Stop all docker containers
docker compose down -v

# Start only the database container and wait for it to be healthy
docker compose up -d db

echo "Czekam na uruchomienie bazy danych..."
# UWAGA: czekamy aż baza przyjmie ZAPYTANIE po tej samej ścieżce, której
# zaraz użyją pg_restore/psql/Django (TCP localhost), a NIE przez
# `docker compose exec db pg_isready`. Przy świeżej inicjalizacji (po
# `down -v`) postgresowy entrypoint odpala najpierw tymczasowy serwer
# tylko na gnieździe UNIX, żeby załadować baseline.sql, i dopiero potem
# restartuje realny serwer nasłuchujący na TCP. W tym oknie
# `pg_isready` wewnątrz kontenera mówi "ready", choć z hosta połączenie
# jeszcze nie wstało — stąd "server closed the connection unexpectedly".
until psql postgres -c 'SELECT 1' > /dev/null 2>&1; do
    sleep 1
done
echo "Baza danych gotowa."

# Obraz bpp_dbserver ma zamontowany baseline.sql w
# /docker-entrypoint-initdb.d/, więc po `down -v` świeży wolumen startuje
# z PEŁNĄ bazą (schema + dane) załadowaną automatycznie przez postgresowy
# entrypoint. Dla restore z dumpu to koliduje ("relacja już istnieje",
# "wielokrotne klucze główne"). Kasujemy więc bazę i tworzymy ją pustą,
# żeby pg_restore trafiał na czysty cel — zgodnie z deklaracją na górze
# skryptu, że odtwarzamy bazę od zera z backupu.
echo "Czyszczę bazę przed odtworzeniem (pomijam baseline.sql z obrazu)..."
psql postgres -c "DROP DATABASE IF EXISTS \"$LOCAL_DATABASE_NAME\" WITH (FORCE);"
psql postgres -c "CREATE DATABASE \"$LOCAL_DATABASE_NAME\";"

# Filter out harmless errors from pg_restore (e.g., unknown config parameters
# from newer PostgreSQL versions)
filter_pg_restore_errors() {
    grep -v "transaction_timeout" >&2
}

if [ "$NO_OWNER" = true ]; then
    pg_restore -j 6 --no-owner -d $LOCAL_DATABASE_NAME "$DUMP_TARGET" \
        2> >(filter_pg_restore_errors) || true
else
    pg_restore -j 6 -d $LOCAL_DATABASE_NAME "$DUMP_TARGET" \
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

# Start all docker containers
docker compose up -d
