# syntax=docker/dockerfile:1

# Build arguments for version flexibility
ARG PYTHON_VERSION=3.12
ARG NODEJS_VERSION=20
ARG DEBIAN_VERSION=trixie

##############################################################################
# BASE: shared foundation for builder and test-runner
##############################################################################
FROM python:${PYTHON_VERSION}-${DEBIAN_VERSION} AS base

ARG NODEJS_VERSION

ENV DEBIAN_FRONTEND=noninteractive

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

RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv sync --frozen --all-extras \
        --no-extra=dev --no-install-project

COPY --chmod=755 docker/bpp_base/sync-deps.sh /usr/local/bin/bpp-sync-deps

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
COPY src/notifications/static/notifications/js/ \
     src/notifications/static/notifications/js/
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

RUN uv run src/manage.py compilemessages -v0 -l pl --traceback

RUN find .venv -type f -name "*.pyc" -delete && \
    python -m compileall -j 0 .venv -x 'wsgiutils' || true

##############################################################################
# TEST-RUNNER: test environment (source mounted at runtime via volume)
##############################################################################
FROM base AS test-runner

# Runtime + test packages (build.txt already in base)
COPY docker/bpp_base/runtime.txt \
     docker/bpp_base/test.txt /tmp/packages/
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=apt-cache \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked,id=apt-lists \
    cat /tmp/packages/*.txt | xargs apt-get install -y

# yarn + grunt (global install for CLI use)
RUN --mount=type=cache,target=/root/.npm,id=npm-cache \
    npm install -g --force yarn grunt-cli

# Playwright system deps
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=apt-cache \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked,id=apt-lists \
    npx playwright install-deps chromium 2>/dev/null || true

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

# Install Python deps to /opt/venv so the docker-compose volume
# mount of .:/src doesn't overwrite them.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /build
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv sync --frozen --all-extras \
        --all-groups --no-install-project

WORKDIR /src

##############################################################################
# RUNTIME: slim production image
##############################################################################
ARG PYTHON_VERSION
ARG DEBIAN_VERSION
FROM python:${PYTHON_VERSION}-slim-${DEBIAN_VERSION} AS runtime

RUN sed -i s/http/https/g /etc/apt/sources.list.d/debian.sources

COPY docker/bpp_base/runtime.txt /tmp/
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /usr/local/bin/uv

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=apt-cache \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked,id=apt-lists \
    apt-get update && \
    xargs -a /tmp/runtime.txt apt-get install -y

ENV PATH="/.venv/bin:$PATH" \
    PYTHONPATH=/src \
    DJANGO_SETTINGS_MODULE=django_bpp.settings.production

WORKDIR /app

COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.venv ./.venv
# The baseline pg_dump (src/baseline-sql) ships along with src/ and is
# loaded by entrypoint-appserver.sh via `manage.py baseline_load` on
# empty databases to skip 800+ migrations on a cold install.
COPY --from=builder /app/src ./src
