#!/bin/sh -e

export PGUSER="${DJANGO_BPP_DB_USER}"
export PGHOST="${DJANGO_BPP_DB_HOST}"
export PGPORT="${DJANGO_BPP_DB_PORT}"
export PGPASSWORD="${DJANGO_BPP_DB_PASSWORD}"

cd /app

# === PHASE 1: Migration (BLOCKING) ===
# baseline_load fast-imports baseline.sql on an empty DB (no-op
# otherwise); migrate then applies the small delta of newer migrations.
echo "Loading baseline (no-op on non-empty DB)..."
python src/manage.py baseline_load || true
echo "Database migrations..."
python src/manage.py migrate
echo "Migrations done."

# === PHASE 2: Background tasks ===
# Static files contract (patrz CLAUDE.md):
#  - builder stage collectstatic'uje do `/app/staticroot.baked` (read-only
#    w obrazie) — runtime NIE odpala collectstatic od nowa, bo to dokladnie
#    ten sam wynik (bez node_modules YarnFinder zwraca pusta liste, wiec
#    output byłby identyczny). `cp -rf` ponizej jest funkcjonalnym
#    zamiennikiem: `.baked` to gotowy output collectstatic.
#  - `$STATIC_ROOT` moze byc overridowane przez deployment (np. bpp-deploy
#    mountuje named volume na `/staticroot`). cp honoruje te zmienna.
#  - `cp -rf` (nie `-u`!) ZAWSZE nadpisuje pliki istniejace w `.baked`.
#    Wczesniej bylo `cp -ru`, ale to puapka: mtime w `.baked` pochodzi z
#    czasu `grunt build` w buildzie obrazu, a mtime na volume z czasu
#    poprzedniego cp przy starcie kontenera. Jesli poprzedni restart byl
#    pozniej niz grunt build w nowym obrazie (typowy przypadek przy szybko
#    nastepujacych po sobie deployach), `-u` skipowal kopiowanie i volume
#    zostawal ze starymi plikami. `-f` to eliminuje.
#  - Pliki ktorych nie ma w `.baked` (tenant-specific zmiany, np. custom
#    branding wgrany post-deploy do podkatalogu nie objetego standardowym
#    collectstatic) nadal przetrwaja, bo cp nie kasuje plikow spoza zrodla.
echo "Starting background tasks..."
(
    if [ -d /app/staticroot.baked ]; then
        echo "  [bg] seeding STATIC_ROOT=$STATIC_ROOT z /app/staticroot.baked..."
        mkdir -p "$STATIC_ROOT"
        cp -rf /app/staticroot.baked/. "$STATIC_ROOT/"
        echo "  [bg] seed done."
    else
        echo "  [bg] UWAGA: /app/staticroot.baked nie istnieje — obraz przed"
        echo "  [bg] wprowadzeniem static files contract. Fallback:"
        echo "  [bg] uruchamiam collectstatic tradycyjnie."
        python src/manage.py collectstatic --noinput -v0 --traceback
    fi

    echo "  [bg] compress..."
    python src/manage.py compress -v0 --force --traceback
    echo "  [bg] compress done."

    echo "  [bg] generate_500_page..."
    python src/manage.py generate_500_page
    echo "  [bg] generate_500_page done."

    echo "  [bg] All background tasks completed."
) &

# === PHASE 3: Start server (immediately) ===
echo "Starting uvicorn..."
if [ "$ENABLE_AUTORELOAD_ON_CODE_CHANGE" = "1" ] || \
   [ "$ENABLE_AUTORELOAD_ON_CODE_CHANGE" = "true" ]; then
    echo "Auto-reload ENABLED"
    exec uvicorn --host 0 --port 8000 --reload \
        --reload-dir /app/src \
        --log-config /uvicorn_log_config.json \
        django_bpp.asgi:application
else
    exec uvicorn --host 0 --port 8000 \
        --log-config /uvicorn_log_config.json \
        django_bpp.asgi:application
fi
