##########################################################################################

FROM python:3.11-bullseye as builder

RUN pip install poetry

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN touch README.md

RUN --mount=type=cache,sharing=locked,target=/var/cache/apt apt update && apt install -y libsasl2-dev python-dev-is-python3 libldap2-dev libssl-dev

RUN --mount=type=cache,target=/root/.cache/pip pip install django-auth-ldap django-microsoft-auth

RUN --mount=type=cache,target=$POETRY_CACHE_DIR poetry install --without dev --all-extras --no-root

##########################################################################################

FROM node:20.14-bullseye as yarn-builder

ENV NODE_ENV=production

COPY package.json yarn.lock ./

RUN --mount=type=cache,target=/root/.yarn YARN_CACHE_FOLDER=/root/.yarn yarn --prod

##########################################################################################

FROM python:3.11-slim-bullseye as runtime

RUN --mount=type=cache,sharing=locked,target=/var/cache/apt apt-get update && apt-get -y install python3-pip libpango-1.0-0 libpangoft2-1.0-0 postgresql-client pandoc curl

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=src

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

COPY --from=yarn-builder node_modules ./node_modules

COPY src ./src
