##########################################################################################

FROM python:3.11.13-trixie AS builder

RUN pip install uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN touch README.md

# RUN --mount=type=cache,sharing=locked,target=/etc/apt/sources.list.d/  \
RUN sed -i s/http/https/g /etc/apt/sources.list.d/debian.sources

# RUN --mount=type=cache,sharing=locked,target=/var/cache/apt  \
RUN apt update && apt install -y libsasl2-dev python-dev-is-python3 libldap2-dev libssl-dev

# Create virtual environment
RUN python -m venv .venv

# Install packages with UV
# RUN --mount=type=cache,target=/root/.cache/uv  \
RUN uv pip install --python .venv django-auth-ldap django-microsoft-auth

# RUN --mount=type=cache,target=/root/.cache/uv  \
RUN uv sync --frozen --all-extras

##########################################################################################

FROM node:20.19-bullseye AS yarn-builder

ENV NODE_ENV=production

COPY package.json yarn.lock ./

RUN --mount=type=cache,target=/root/.yarn YARN_CACHE_FOLDER=/root/.yarn yarn --prod

##########################################################################################

FROM python:3.11.13-slim-trixie AS runtime

# RUN --mount=type=cache,sharing=locked,target=/etc/apt/sources.list.d/  \
RUN sed -i s/http/https/g /etc/apt/sources.list.d/debian.sources

# RUN --mount=type=cache,sharing=locked,target=/var/cache/apt apt-get update &&  \
RUN apt update && apt install -y python3-pip libpango-1.0-0 libpangoft2-1.0-0 postgresql-client pandoc curl gettext

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=src

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

COPY --from=yarn-builder node_modules ./node_modules

COPY src ./src
