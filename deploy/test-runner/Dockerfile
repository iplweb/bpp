# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.13
ARG NODEJS_VERSION=22

FROM python:${PYTHON_VERSION}-slim

ARG NODEJS_VERSION

ENV DEBIAN_FRONTEND=noninteractive

# uv (cached pip install)
RUN --mount=type=cache,target=/root/.cache/pip,id=pip-cache \
    pip install uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# System libraries (matching .github/workflows/tests.yml)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=apt-cache \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked,id=apt-lists \
    apt-get update && apt-get install -y \
        build-essential \
        libpq-dev \
        git \
        gettext \
        libldap2-dev \
        libsasl2-dev \
        libcairo2-dev \
        libssl-dev \
        redis-tools \
        curl \
        gnupg \
        postgresql-client \
    && curl -fsSL https://deb.nodesource.com/setup_${NODEJS_VERSION}.x | bash - \
    && apt-get install -y nodejs

# yarn + grunt (cached npm install)
RUN --mount=type=cache,target=/root/.npm,id=npm-cache \
    npm install -g --force yarn grunt-cli

# Playwright system deps (cached apt)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=apt-cache \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked,id=apt-lists \
    npx playwright install-deps chromium 2>/dev/null || true

WORKDIR /src

# Install Python deps first (cached by uv).
# pyproject.toml + uv.lock copied for layer caching;
# full source is mounted at runtime via docker-compose volume.
COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv sync --frozen --all-extras --no-install-project
