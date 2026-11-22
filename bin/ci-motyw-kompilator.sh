#!/usr/bin/env bash
# Prawdziwy kompilator motywów (konfigurator wyglądu) dla testów w CI.
#
# Obraz test-runner w CI jest odchudzony — bez Node'a — ale ma zbudowane
# zasoby kompilatora (grunt: shell:esbuildSass + motywyZrodla). Wyciągamy je
# z obrazu i uruchamiamy serwis `motyw-kompilator` (docker-compose.test.ci.yml:
# oficjalny node:22-alpine, pliki tylko do odczytu — jak w bpp-deploy,
# gdzie ten sam obraz czyta je z wolumenu plików statycznych). Testy rozmawiają z nim przez HTTP — tą samą ścieżką co produkcja
# (DJANGO_BPP_MOTYW_KOMPILATOR_URL).
#
# Wymaga zmiennej COMPOSE_FILES (jak pozostałe kroki workflow testów).
set -euo pipefail

: "${COMPOSE_FILES:?ustaw COMPOSE_FILES (np. -f docker-compose.test.yml -f docker-compose.test.ci.yml)}"
KATALOG=ci-motyw-kompilator

rm -rf "$KATALOG"
mkdir -p "$KATALOG"
# shellcheck disable=SC2086  # COMPOSE_FILES to lista flag
docker compose $COMPOSE_FILES run --rm --no-deps -T test-runner \
    tar -C /src/src/bpp/static/bpp/js -cf - \
        motyw-konfig.js motyw-kompilator.js motyw-kompilator-serwer.js \
        dist/sass-przegladarka.js dist/motyw-zrodla-scss.json \
    | tar -C "$KATALOG" -xf -

# Pull z ponowieniami (Docker Hub bywa niestabilny), potem start.
n=0
# shellcheck disable=SC2086
until docker compose $COMPOSE_FILES pull motyw-kompilator; do
    n=$((n + 1))
    if [ "$n" -ge 3 ]; then
        echo "pull motyw-kompilator nie powiodl sie po $n probach" >&2
        exit 1
    fi
    echo "pull motyw-kompilator padl (proba $n), ponawiam za 10s..." >&2
    sleep 10
done
# shellcheck disable=SC2086
docker compose $COMPOSE_FILES up -d motyw-kompilator

for _ in $(seq 1 30); do
    # shellcheck disable=SC2086
    if docker compose $COMPOSE_FILES exec -T motyw-kompilator \
        wget -qO- http://127.0.0.1:8095/zdrowie >/dev/null 2>&1; then
        echo "motyw-kompilator gotowy"
        exit 0
    fi
    sleep 1
done
echo "motyw-kompilator nie odpowiada" >&2
# shellcheck disable=SC2086
docker compose $COMPOSE_FILES logs motyw-kompilator >&2
exit 1
