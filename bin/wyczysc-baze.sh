#!/bin/bash
set -euo pipefail

# Ten skrypt:
# 1) usuwa bazę danych bpp (jeśli istnieje)
# 2) tworzy nową, pustą bazę danych
# 3) uruchamia migracje Django, tworząc strukturę tabel
#
# Uwaga: Ten skrypt utworzy PUSTĄ instalację BPP bez żadnych danych!

BASEDIR=$(dirname "$0")

LOCAL_DATABASE_NAME=bpp

echo "==========================================="
echo "UWAGA: Ten skrypt usunie WSZYSTKIE dane"
echo "z bazy danych '$LOCAL_DATABASE_NAME' i utworzy"
echo "pustą instalację!"
echo "==========================================="
echo ""
read -p "Czy na pewno chcesz kontynuować? (tak/nie): " -r
echo ""

if [[ ! $REPLY =~ ^[Tt]ak$ ]]; then
    echo "Anulowano."
    exit 1
fi

echo "Usuwanie istniejącej bazy danych (jeśli istnieje)..."
dropdb -f --if-exists $LOCAL_DATABASE_NAME

echo "Tworzenie nowej, pustej bazy danych..."
createdb $LOCAL_DATABASE_NAME

echo "Tworzenie użytkowników PostgreSQL (jeśli nie istnieją)..."
createuser -s mimooh || true
createuser -s bpp || true

cd "$BASEDIR/.."

echo "Uruchamianie migracji Django..."
python src/manage.py migrate

echo "Aktualizacja domeny django_site dla środowiska deweloperskiego..."
psql $LOCAL_DATABASE_NAME -c "UPDATE django_site SET domain='127.0.0.1:8000' WHERE id=1;" || true

echo ""
echo "==========================================="
echo "Zakończono pomyślnie!"
echo ""
echo "Utworzono pustą bazę danych '$LOCAL_DATABASE_NAME'"
echo ""
echo "Możesz uruchomić serwer deweloperski:"
echo "  python src/manage.py runserver"
echo "==========================================="
