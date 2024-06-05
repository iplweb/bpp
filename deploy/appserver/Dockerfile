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

RUN --mount=type=cache,target=$POETRY_CACHE_DIR poetry install --without dev --no-root

##########################################################################################

FROM node:20.14-bullseye as yarn-builder

COPY package.json yarn.lock ./

RUN yarn

##########################################################################################

FROM python:3.11-slim-bullseye as runtime

RUN apt-get update && apt-get -y install python3-pip libpango-1.0-0 libpangoft2-1.0-0 postgresql-client

RUN pip install uvicorn

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=src

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

COPY --from=yarn-builder node_modules ./node_modules

COPY src ./src

RUN DATABASE_URL=postgres://whatever@whenever:5432/anydb python src/manage.py collectstatic --noinput

EXPOSE 8000

COPY --chmod=755 deploy/appserver/entrypoint-appserver.sh /
COPY --chmod=755 deploy/appserver/entrypoint-workserver.sh /

ENTRYPOINT ["/entrypoint-appserver.sh"]
