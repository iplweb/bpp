# syntax=docker/dockerfile:1

# Build arguments for version flexibility
ARG PYTHON_VERSION=3.12
ARG NODEJS_VERSION=20
ARG DEBIAN_VERSION=trixie
# Pandoc installed via COPY --from= zamiast apt-get, bo apt-owy pandoc
# ciagnie pandoc-data i transitive deps (~300 MB). Osobny pinned tag
# pozwala trzymac pandoc w stabilnej warstwie cache, niezaleznej od
# rebuildow bpp. Update pandoc = zmiana tego jednego arg.
ARG PANDOC_VERSION=3.5

##############################################################################
# PANDOC-SRC: pinned pandoc binary source
# Oddzielny stage bo BuildKit nie rozwija zmiennych w `COPY --from=image:${VAR}`.
##############################################################################
FROM pandoc/core:${PANDOC_VERSION}-ubuntu AS pandoc-src

##############################################################################
# BASE: shared foundation for builder and test-runner
##############################################################################
FROM python:${PYTHON_VERSION}-${DEBIAN_VERSION} AS base

ARG NODEJS_VERSION

ENV DEBIAN_FRONTEND=noninteractive

# MALLOC_ARENA_MAX ogranicza liczbę aren glibc malloc. Domyślnie glibc tworzy do
# 8*CPU aren, co przy wielowątkowych procesach Pythona z rozszerzeniami C
# (numpy, pandas, psycopg2, lxml, openpyxl, Pillow, weasyprint) prowadzi do
# silnej fragmentacji i rozdęcia RSS — zwolniona pamięć rzadko wraca do OS.
# Ograniczenie do 2 aren typowo ścina RSS o 20-40% na proces (web + każdy
# prefork-child Celery) kosztem nieznacznie większej kontencji alokatora.
# Dziedziczone przez stage `testserver` (dev). Stage `runtime` (prod) ustawia
# to samo osobno, bo nie wywodzi się z `base`.
ENV MALLOC_ARENA_MAX=2

COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN sed -i s/http/https/g /etc/apt/sources.list.d/debian.sources

COPY docker/bpp_base/build.txt /tmp/
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=apt-cache \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked,id=apt-lists \
    apt-get update && \
    xargs -a /tmp/build.txt apt-get install -y && \
    curl -fsSL \
        https://deb.nodesource.com/setup_${NODEJS_VERSION}.x \
        | bash - && \
    apt-get install -y nodejs

##############################################################################
# BUILDER: production build (bakes source into image)
##############################################################################
FROM base AS builder

WORKDIR /app

COPY pyproject.toml uv.lock yarn.lock package.json ./

# R4: `--no-dev` blokuje grupe [dependency-groups].dev (testowe deps,
# ruff, ipython, playwright, run-site, vulture itd.). Wczesniej dev byl
# extras-em i `--all-extras --no-extra=dev` ciagal jeszcze
# `baseline-rebuild`; po migracji dev->dependency-group wymieniamy tylko
# realnie potrzebne extras produkcji (ldap, office365).
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv sync --frozen --no-dev --no-install-project \
        --extra ldap --extra office365

# R6: pygad deklaruje matplotlib jako twardą dep dla funkcji rysowania
# zbieżności algorytmu genetycznego (plot_fitness), których BPP nie używa.
# matplotlib jest importowane lazy wewnątrz tych funkcji, więc usunięcie go
# nie psuje `import pygad`. Oszczędność: ~38 MB (matplotlib + contourpy +
# kiwisolver + cycler). fonttools zostaje — używa go weasyprint i pyphen.
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv pip uninstall --python /app/.venv/bin/python \
        matplotlib contourpy kiwisolver cycler

RUN --mount=type=cache,target=/root/.npm,id=npm-cache \
    --mount=type=cache,target=/root/.yarn,id=yarn-cache \
    npx yarn install --dev --ignore-optional && \
    npx yarn add grunt

# ---- Static assets for grunt build ----
# These COPYs are separate from the main COPY . . so that grunt build
# is cached when only Python code changes (saves ~1-2 min on hotfixes).
# When adding a new SCSS task to Gruntfile.js, add a COPY here too.
COPY Gruntfile.js ./
# Theme and admin SCSS
COPY src/bpp/static/scss/ src/bpp/static/scss/
COPY src/bpp/static/bpp/scss/ src/bpp/static/bpp/scss/
# JS for esbuild bundle
COPY src/bpp/static/bpp/js/ src/bpp/static/bpp/js/
# JS for esbuild bundle eksploratora powiązań (cytoscape-entry + moduły ES)
COPY src/powiazania_autorow/static/powiazania_autorow/js/ \
     src/powiazania_autorow/static/powiazania_autorow/js/
# App-specific SCSS (keep alphabetical)
COPY src/bpp_setup_wizard/static/bpp_setup_wizard/scss/ \
     src/bpp_setup_wizard/static/bpp_setup_wizard/scss/
COPY src/deduplikator_autorow/static/deduplikator_autorow/scss/ \
     src/deduplikator_autorow/static/deduplikator_autorow/scss/
COPY src/deduplikator_zrodel/static/deduplikator_zrodel/scss/ \
     src/deduplikator_zrodel/static/deduplikator_zrodel/scss/
COPY src/ewaluacja_dwudyscyplinowcy/static/ewaluacja_dwudyscyplinowcy/scss/ \
     src/ewaluacja_dwudyscyplinowcy/static/ewaluacja_dwudyscyplinowcy/scss/
COPY src/ewaluacja_liczba_n/static/ewaluacja_liczba_n/scss/ \
     src/ewaluacja_liczba_n/static/ewaluacja_liczba_n/scss/
COPY src/ewaluacja_optymalizuj_publikacje/static/ewaluacja_optymalizuj_publikacje/scss/ \
     src/ewaluacja_optymalizuj_publikacje/static/ewaluacja_optymalizuj_publikacje/scss/
COPY src/komparator_publikacji_pbn/static/komparator_publikacji_pbn/scss/ \
     src/komparator_publikacji_pbn/static/komparator_publikacji_pbn/scss/
COPY src/pbn_downloader_app/static/pbn_downloader_app/scss/ \
     src/pbn_downloader_app/static/pbn_downloader_app/scss/
COPY src/pbn_export_queue/static/pbn_export_queue/scss/ \
     src/pbn_export_queue/static/pbn_export_queue/scss/
COPY src/pbn_import/static/pbn_import/scss/ \
     src/pbn_import/static/pbn_import/scss/
COPY src/pbn_komparator_zrodel/static/pbn_komparator_zrodel/scss/ \
     src/pbn_komparator_zrodel/static/pbn_komparator_zrodel/scss/
COPY src/przemapuj_prace_autora/static/przemapuj_prace_autora/scss/ \
     src/przemapuj_prace_autora/static/przemapuj_prace_autora/scss/
COPY src/przemapuj_zrodla_pbn/static/przemapuj_zrodla_pbn/scss/ \
     src/przemapuj_zrodla_pbn/static/przemapuj_zrodla_pbn/scss/

RUN npx grunt build-non-interactive

RUN rm -rf node_modules

RUN --mount=type=cache,target=/root/.npm,id=npm-cache \
    --mount=type=cache,target=/root/.yarn,id=yarn-cache \
    npx yarn install --prod

# ---- Full source code (busts cache on any code change) ----
# Generated CSS/JS files are gitignored, so COPY won't overwrite them.
ARG GIT_SHA=unknown
RUN echo "Building from git commit: ${GIT_SHA}"

COPY . .

RUN /app/.venv/bin/python src/manage.py compilemessages -v0 -l pl --traceback

# R5: collectstatic wymaga `node_modules` przez YarnFinder — uruchamiamy
# go teraz, w builder stage, aby staticroot był pre-populowany, a runtime
# mógł shipować tylko `/app/staticroot.baked` zamiast 300+ MB node_modules.
# Zapisujemy do `.baked` (nie `/app/staticroot`), bo runtime `STATIC_ROOT`
# moze byc overridowane przez deployment (np. bpp-deploy mountuje named
# volume na `/staticroot`). Entrypoint appservera kopiuje `.baked → $STATIC_ROOT`
# przy starcie — kontrakt opisany w CLAUDE.md (sekcja "Static files contract").
# collectstatic nie potrzebuje DB ani Redisa; wystarczy dummy SECRET_KEY.
# UWAGA: musi biec PRZED R2 — src/import_pracownikow/static/.../przyklad.xlsx
# to symlink do src/import_pracownikow/tests/testdata.xlsx; collectstatic
# rozwiązuje symlink (kopiuje treść) i dopiero potem możemy usunąć tests/.
# R11: --ignore sinon --ignore qunit wycina test-only biblioteki JS
# (sinon/pkg/sinon.js + qunit/qunit/*) z production staticroot. Dev flow
# jest nietknięty, bo używamy collectstatic tylko w buildzie obrazu.
# R14: --ignore '*.map' wycina source maps (~8 MB rozsianych po
# foundation-sites, tone, djangoql, rest_framework, bpp/js/dist, ...).
# Source maps sluza tylko browser devtools podczas debugowania JS/CSS;
# w prod 404 na .map pojawia sie w konsoli gdy user otworzy devtools —
# bez wplywu na dzialanie aplikacji.
RUN DJANGO_BPP_SECRET_KEY=build-time-only-not-used \
    STATIC_ROOT=/app/staticroot.baked \
    /app/.venv/bin/python src/manage.py collectstatic \
        --noinput -v0 --traceback \
        --ignore sinon --ignore qunit --ignore '*.map'

RUN rm -rf /app/node_modules

# R2: testy i pytest-only fixture package nie są potrzebne w produkcji.
# UWAGA: NIE usuwamy:
#  - /app/src/test_bpp — to INSTALLED_APP wymagany nawet w produkcji
#    (modele używane przez aplikację `long_running`, patrz komentarz w
#    src/django_bpp/settings/base.py)
#  - src/*/fixtures/ — to katalogi Django loaddata fixtures z danymi
#    produkcyjnymi (charakter_formalny.json, typ_odpowiedzialnosci.json
#    itp. — referencje w migracjach).
# Usuwamy tylko katalogi `tests` na poziomie app (depth 2) i szczegółowe
# ścieżki pytest-owe. Musi biec PO collectstatic — patrz komentarz wyżej.
RUN find /app/src -mindepth 2 -type d -name tests -exec rm -rf {} + && \
    rm -rf /app/src/fixtures \
           /app/src/conftest.py \
           /app/src/integration_tests

# R13: analogicznie do R12, usuwamy .pyc z /app/src (~2 MB). Bytecode
# zostaje skompilowany przez compilemessages + collectstatic powyzej;
# runtime kompiluje on-demand przy pierwszym imporcie, kolejne workery
# dziela bytecode przez fork() (gunicorn preload).
RUN find /app/src -type d -name __pycache__ -exec rm -rf {} + \
    2>/dev/null || true

# R3: UV_COMPILE_BYTECODE=1 już wygenerowało .pyc podczas `uv sync`.
# Dodatkowo strippujemy katalogi test* z wbudowanych pakietów, aby
# zaoszczędzić kilkanaście MB (Django zachowujemy — template'y odwołują
# się wewnętrznie do testowych aplikacji).
RUN find /app/.venv -type d -name tests -not -path "*/django/*" \
      -exec rm -rf {} + 2>/dev/null || true

# R8: strip debug symbols z .so w venv (~180 MB .so total, ~30-50 MB zysku).
# `--strip-unneeded` zachowuje symbole potrzebne do dynamic linking
# (inaczej `--strip-all` dalby ImportError), wycina tylko debug info i
# local symbols. binutils (strip) jest juz w python:3.12-trixie. Warning
# swallowing: niektore wheels moga miec non-ELF .so (fallback Python
# impl, np. w setuptools).
RUN find /app/.venv -name "*.so" -exec strip --strip-unneeded {} + \
    2>/dev/null || true

# R12: usun __pycache__ w venv (~118 MB). UV_COMPILE_BYTECODE=1 generuje
# .pyc przy `uv sync`, ale w produkcji wolimy mniejszy obraz kosztem
# wolniejszego cold startu pierwszego workera (Python kompiluje .pyc
# in-memory przy pierwszym imporcie). Kolejne workery dzielą skompilowany
# bytecode przez fork() (gunicorn) albo preload, wiec efekt jest tylko
# na pierwszym starcie procesu.
RUN find /app/.venv -type d -name __pycache__ -exec rm -rf {} + \
    2>/dev/null || true

##############################################################################
# TEST-RUNNER: test environment (source mounted at runtime via volume)
##############################################################################
# TEST-VENV-BUILDER: kompiluje testowy venv (--all-extras --all-groups) i
# pobiera przegladarki Playwright NA PELNYM python:trixie (z toolchainem),
# bo wheelsy z C-rozszerzeniami wymagajacymi kompilacji ze zrodel
# (python-ldap z extras `ldap`) potrzebuja gcc + naglowkow z build.txt.
# Artefakty (/opt/venv, /opt/playwright) sa COPY-owane do slim test-runnera
# nizej — to wzorzec identyczny jak produkcyjny stage `runtime`, dzieki
# ktoremu ~1.1 GB toolchainu (buildpack python:trixie + build.txt) NIE laduje
# w obrazie testowym.
FROM base AS test-venv-builder

ENV UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /build
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv sync --frozen --all-extras \
        --all-groups --no-install-project

# Przegladarki Playwright raz, do /opt/playwright (kopiowane do slim nizej).
RUN PLAYWRIGHT_BROWSERS_PATH=/opt/playwright \
    /opt/venv/bin/playwright install chromium chromium-headless-shell


##############################################################################
# TEST-RUNNER: srodowisko testowe NA python:slim. Skompilowany venv +
# przegladarki przychodza gotowe z `test-venv-builder` (COPY --from), wiec slim
# nie potrzebuje toolchainu. Tnie to obraz o ~1.1 GB build-only deps (buildpack
# pelnego python:trixie: gcc/g++/dpkg-dev/autoconf + git/mercurial/svn, plus
# nasz build.txt), ktore byly martwym balastem w obrazie testowym. Wzorzec
# identyczny jak produkcyjny stage `runtime` (compiled venv na slim + runtime
# liby). Slim NIE dziedziczy z `base`, wiec ENV/uv/node trzeba odtworzyc.
##############################################################################
ARG PYTHON_VERSION
ARG DEBIAN_VERSION
FROM python:${PYTHON_VERSION}-slim-${DEBIAN_VERSION} AS test-runner

ARG NODEJS_VERSION

ENV DEBIAN_FRONTEND=noninteractive
# MALLOC_ARENA_MAX: patrz komentarz w stage `base` (slim nie dziedziczy).
ENV MALLOC_ARENA_MAX=2
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
ENV PATH="/opt/venv/bin:${PATH}"

# uv potrzebne w runtime — CI wola `uv run pytest` (jak na pelnym obrazie).
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /usr/local/bin/uv

RUN sed -i s/http/https/g /etc/apt/sources.list.d/debian.sources

# Runtime liby wspoldzielone, ktorych potrzebuja skompilowane wheelsy +
# narzedzia. runtime.txt: pango/cairo (weasyprint), libpq, gmp/lua (pandoc).
# test.txt: redis-tools. Dodatkowo wzgledem `base`/produkcji:
#  - libldap2/libsasl2-2: python-ldap (z extras `ldap`) linkuje sie z nimi;
#    na pelnym trixie dawal je libldap2-dev/libsasl2-dev (build.txt), tu nie ma,
#  - gettext: msgfmt do compilemessages (bake nizej),
#  - ca-certificates/curl/gnupg: repo NodeSource + Dockera,
#  - git: `yarn install` ma zaleznosci po URL-u git (pelny trixie mial git
#    w buildpacku; slim nie ma) — bez tego `yarn install` pada.
COPY docker/bpp_base/runtime.txt docker/bpp_base/test.txt /tmp/packages/
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=apt-cache \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked,id=apt-lists \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg gettext git libldap2 libsasl2-2 && \
    cat /tmp/packages/*.txt | xargs apt-get install -y

# Node (grunt build + yarn install dla `make assets`) + yarn/grunt globalnie.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=apt-cache \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked,id=apt-lists \
    curl -fsSL https://deb.nodesource.com/setup_${NODEJS_VERSION}.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g --force yarn grunt-cli

# Skompilowany venv + przegladarki z buildera (bez toolchainu).
COPY --from=test-venv-builder /opt/venv /opt/venv
COPY --from=test-venv-builder /opt/playwright /opt/playwright

# Playwright system deps. Na slim — w odroznieniu od pelnego trixie — tych
# bibliotek nie ma, wiec instalacja jest konieczna (uzywamy playwrighta z venv).
RUN /opt/venv/bin/playwright install-deps chromium

# Docker CLI (for tests that use Docker, e.g. html2docx)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=apt-cache \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked,id=apt-lists \
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg \
        -o /etc/apt/keyrings/docker.asc && \
    echo "deb [arch=$(dpkg --print-architecture) \
        signed-by=/etc/apt/keyrings/docker.asc] \
        https://download.docker.com/linux/debian \
        $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
        > /etc/apt/sources.list.d/docker.list && \
    apt-get update && apt-get install -y docker-ce-cli

# Pandoc z oficjalnego obrazu (patrz komentarz R7 przy runtime stage).
# libgmp10/liblua5.4-0 juz sa w runtime.txt instalowanym wyzej.
COPY --from=pandoc-src /usr/local/bin/pandoc /usr/local/bin/pandoc

# Yarn deps + grunt CLI (needed for `make assets`). Mirrors the
# testserver stage so CI gets a pre-built test-runner image with the
# same toolchain available offline.
WORKDIR /src
COPY package.json yarn.lock Gruntfile.js ./
RUN --mount=type=cache,target=/root/.npm,id=npm-cache \
    --mount=type=cache,target=/root/.yarn,id=yarn-cache \
    npx yarn install --dev --ignore-optional && \
    npx yarn add grunt

# Snapshot the source tree and bake the frontend assets + .mo
# translations into the image. CI consumes this through the
# docker-compose.test.ci.yml override (no bind mount), so each test
# job pulls a ready-to-run image instead of running `make assets`
# (~1 min × N jobs) on every invocation. Local dev keeps the bind
# mount and rebuilds assets on demand.
#
# Cache-bust źródła per commit — TAK SAMO jak builder przed `COPY . .`
# (patrz `RUN echo "Building from git commit..."`). Powód: ten obraz jest
# budowany z `cache-from type=registry,ref=...:cache`, które potrafi
# przywrócić STARĄ warstwę `COPY src/` sprzed zmiany zawartości src/ (np.
# przeniesienia plików). Wtedy `grunt build` / esbuild biegnie na
# nieaktualnym drzewie i nie widzi nowo dodanych/przeniesionych plików
# (objaw: esbuild "Could not resolve <nowa ścieżka>"). RUN z $GIT_SHA zmienia
# klucz cache co commit i wymusza świeży COPY + grunt. Koszt: warstwa źródła
# test-runnera odbudowuje się na każdym commicie (sekundy), ale CI dostaje
# obraz z aktualnym kodem i assetami.
ARG GIT_SHA=unknown
RUN echo "test-runner source snapshot for ${GIT_SHA}"

COPY src/ /src/src/
COPY baseline-sql/ /src/baseline-sql/
COPY conftest.py pytest.ini Makefile pyproject.toml uv.lock /src/

RUN npx grunt build-non-interactive
RUN /opt/venv/bin/python src/manage.py compilemessages -v0 -l pl --traceback

##############################################################################
# TESTSERVER: lokalny obraz developerski (NIE jest publikowany do registry)
#
# Buduj: docker compose build (NIGDY przez docker buildx bake — ten target
# swiadomie nie istnieje w docker-bake.hcl, dzieki czemu CI go nie pushuje).
# Cel: dev-friendly obraz dla appserver/celerybeat/worker/denorm-queue
# uruchamianych przez docker-compose.yml. Source code mountowany przez
# bind-mount, .venv zyje w /opt/venv (poza /app/src), wiec bind-mount nie
# shadowuje deps i uv sync nie jest potrzebny przy starcie kontenera.
#
# Roznica vs runtime (production):
#  - Pelne extras + dev group (--all-extras --all-groups): testcontainers,
#    pytest, vulture, pytest-repeat itd. dla rzeczy uruchamianych w kontenerze.
#  - uv pozostaje, .venv w /opt/venv (nie /app/.venv).
#  - Brak strip/rm tests/__pycache__/-debug-symbols (to optymalizacje rozmiaru,
#    niepotrzebne lokalnie).
#  - Wszystkie entrypointy skopiowane do /; docker-compose wybiera per-service
#    przez `entrypoint:`. Ten stage celowo NIE definiuje wlasnego ENTRYPOINT.
##############################################################################
FROM base AS testserver

# Runtime + test apt packages (jak test-runner). build.txt jest juz w base.
COPY docker/bpp_base/runtime.txt \
     docker/bpp_base/test.txt /tmp/packages/
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=apt-cache \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked,id=apt-lists \
    apt-get update && \
    cat /tmp/packages/*.txt | xargs apt-get install -y

# Pandoc z oficjalnego obrazu (patrz komentarz R7 przy runtime stage).
COPY --from=pandoc-src /usr/local/bin/pandoc /usr/local/bin/pandoc

# yarn + grunt CLI dla developera w kontenerze.
RUN --mount=type=cache,target=/root/.npm,id=npm-cache \
    npm install -g --force yarn grunt-cli

# Docker CLI dla testow ktore wolaja docker (html2docx, testcontainers).
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=apt-cache \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked,id=apt-lists \
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg \
        -o /etc/apt/keyrings/docker.asc && \
    echo "deb [arch=$(dpkg --print-architecture) \
        signed-by=/etc/apt/keyrings/docker.asc] \
        https://download.docker.com/linux/debian \
        $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
        > /etc/apt/sources.list.d/docker.list && \
    apt-get update && apt-get install -y docker-ce-cli

# Deps do /opt/venv. Bind-mount source do /app/src (z docker-compose.yml) nie
# tknie venva — inny prefix sciezki, dlatego nie potrzeba named volume na .venv.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH=/app/src \
    DJANGO_SETTINGS_MODULE=django_bpp.settings.production \
    STATIC_ROOT=/app/staticroot

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv sync --frozen --all-extras --all-groups --no-install-project

# Yarn + grunt + collectstatic — mirror production builder, zeby:
# 1. /app/staticroot.baked istnial → entrypoint-appserver.sh przy starcie wybiera
#    szybki `cp -ru .baked -> $STATIC_ROOT` zamiast pelnego collectstatic
#    (ktore wymaga /app/node_modules przez custom YarnFinder, src/bpp/finders.py).
# 2. node_modules zostalo w obrazie (vs production, ktora je kasuje) → developer
#    moze odpalic `docker compose exec appserver npx grunt build` po edycji SCSS.
COPY package.json yarn.lock Gruntfile.js ./
RUN --mount=type=cache,target=/root/.npm,id=npm-cache \
    --mount=type=cache,target=/root/.yarn,id=yarn-cache \
    npx yarn install --dev --ignore-optional && \
    npx yarn add grunt

# Snapshot src/ dla grunt build + collectstatic. Cache invalidation na zmiane
# dowolnego pliku w src/ jest akceptowalny w dev: yarn install (powyzej) i tak
# zostaje cached, a grunt + collectstatic licza sie ~minute lacznie.
# Runtime przykrywa ten snapshot bind-mountem `./src:/app/src` z compose.
COPY src/ src/
COPY baseline-sql/ baseline-sql/

RUN npx grunt build-non-interactive

# collectstatic do .baked (kontrakt static files z CLAUDE.md). Dummy SECRET_KEY
# wystarcza — collectstatic nie wymaga DB ani Redisa. Bez --ignore sinon/qunit/
# *.map — zostawiamy w dev, latwiej debugowac.
RUN DJANGO_BPP_SECRET_KEY=build-time-only-not-used \
    STATIC_ROOT=/app/staticroot.baked \
    python src/manage.py collectstatic \
        --noinput -v0 --traceback

# Entrypointy dla wszystkich uslug — docker-compose wybiera wlasciwy per-service.
COPY --chmod=755 docker/appserver/entrypoint-appserver.sh \
                 /entrypoint-appserver.sh
COPY --chmod=755 docker/beatserver/entrypoint-beatserver.sh \
                 /entrypoint-beatserver.sh
COPY --chmod=755 docker/workerserver/entrypoint-workerserver.sh \
                 /entrypoint-workerserver.sh
COPY --chmod=755 docker/denorm-queue/entrypoint-denorm-queue.sh \
                 /entrypoint-denorm-queue.sh
COPY --chmod=644 docker/appserver/uvicorn_log_config.json \
                 /uvicorn_log_config.json
COPY --chmod=644 docker/appserver/gunicorn_conf.py \
                 /gunicorn_appserver_conf.py

##############################################################################
# RUNTIME: slim production image
##############################################################################
ARG PYTHON_VERSION
ARG DEBIAN_VERSION
FROM python:${PYTHON_VERSION}-slim-${DEBIAN_VERSION} AS runtime

# Bake'a przekazuje GIT_SHA z `--set "base.args.GIT_SHA=..."`. Nadpisanie
# możliwe dla lokalnych buildów; default `unknown` zostaje, kiedy nikt nie
# poda wartości. BPP_BUILD_FLAVOR rozróżnia release (master) od dev (PR/feature)
# — pokazujemy SHA w stopce tylko poza release-em. BPP_IMAGE_TAG to kanoniczny
# tag obrazu (np. "119-merge"), który workflow promuje po skanie Trivy.
ARG GIT_SHA=unknown
ARG BPP_BUILD_FLAVOR=dev
ARG BPP_IMAGE_TAG=unknown
# Sanityzowana nazwa source brancha (alias) — workflow ustawia tylko dla
# pull_request eventów. Dla master/feature push pozostaje pusty.
ARG BPP_BRANCH_TAG=

RUN sed -i s/http/https/g /etc/apt/sources.list.d/debian.sources

COPY docker/bpp_base/runtime.txt /tmp/

# R1: `uv` nie jest potrzebny do uruchamiania aplikacji — entrypointy
# używają `python`/`celery`/`uvicorn`/`gunicorn` bezpośrednio z .venv/bin,
# a wszystkie zależności (watchdog dla --reload, gunicorn dla authserver)
# są deklarowane w pyproject.toml. uv zostaje w stage `builder`/`test-runner`.

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=apt-cache \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked,id=apt-lists \
    apt-get update && \
    xargs -a /tmp/runtime.txt apt-get install -y && \
    rm -rf /usr/share/doc/* /usr/share/man/* /var/lib/apt/lists/*
# R15: rm /usr/share/{doc,man}/* + /var/lib/apt/lists/* (~3.4 MB).
# Standardowy docker-slim pattern — runtime nigdy nie czyta README,
# changelog.Debian.gz ani copyright. apt-lists i tak jest w cache mount,
# ale explicite rm to defensive (BuildKit zostawia czasem residual).

# R7: pandoc binary z oficjalnego obrazu pandoc/core zamiast apt (~300 MB
# oszczednosci + stabilna warstwa cache, niezalezna od rebuildow bpp).
# Binary linkuje dynamicznie do libgmp10, liblua5.4-0 (w runtime.txt).
COPY --from=pandoc-src /usr/local/bin/pandoc /usr/local/bin/pandoc

# Uwaga: wcześniej PATH wskazywał na /.venv/bin, a venv jest pod
# /app/.venv — działało to tylko dlatego, że wszystkie komendy w
# entrypointach zaczynały się od `uv run`, które samo znajdowało venv
# po pyproject.toml. Po usunięciu `uv run` (R1) PATH musi wskazywać na
# właściwy katalog venvu.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    DJANGO_SETTINGS_MODULE=django_bpp.settings.production \
    STATIC_ROOT=/app/staticroot \
    BPP_GIT_SHA=${GIT_SHA} \
    BPP_BUILD_FLAVOR=${BPP_BUILD_FLAVOR} \
    BPP_IMAGE_TAG=${BPP_IMAGE_TAG} \
    BPP_BRANCH_TAG=${BPP_BRANCH_TAG} \
    MALLOC_ARENA_MAX=2
# MALLOC_ARENA_MAX=2: patrz komentarz w stage `base`. Ustawiane też tutaj, bo
# `runtime` startuje od czystego python:slim (nie dziedziczy z `base`).
# Dotyczy WSZYSTKICH serwisów (appserver + workery Celery + beat + denorm),
# które wywodzą się z iplweb/bpp_base = ten stage.

WORKDIR /app

# R5: zamiast 300+ MB node_modules shipujemy pre-populowany /app/staticroot.baked
# wygenerowany przez collectstatic w builder stage. Entrypoint appservera
# kopiuje `.baked -> $STATIC_ROOT` przy starcie — pozwala to deploymentom
# (bpp-deploy) overridowac STATIC_ROOT na wlasny named volume, a nadal
# dostac pre-populowane pliki bez uruchamiania collectstatic od zera.
# Kontrakt: `/app/staticroot.baked` to read-only shipowane pliki; runtime
# pisze do `$STATIC_ROOT` (default `/app/staticroot`, override w compose).
COPY --from=builder /app/staticroot.baked ./staticroot.baked
COPY --from=builder /app/.venv ./.venv
# The baseline pg_dump (baseline-sql/) is a separate data artifact at the
# repo root. Entrypoint-appserver.sh loads it via `manage.py baseline_load`
# on empty databases to skip 800+ migrations on a cold install.
COPY --from=builder /app/src ./src
COPY --from=builder /app/baseline-sql ./baseline-sql

# Sanity-check: zapisuje GIT_SHA do pliku, żeby `cat /app/.git-sha`
# w runtime od razu pokazywał commit, na podstawie którego zbudowano obraz.
# Diagnozuje sytuacje, w których pull tagu zwraca nieoczekiwaną treść
# (np. nie ten PR/branch). Pisane PO wszystkich `COPY --from=builder`,
# żeby nie zostało nadpisane.
RUN echo "${GIT_SHA}" > /app/.git-sha
