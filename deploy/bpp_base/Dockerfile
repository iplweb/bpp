# Build arguments for version flexibility
ARG PYTHON_VERSION=3.12
ARG NODEJS_VERSION=20
ARG DEBIAN_VERSION=trixie

##########################################################################################

FROM python:${PYTHON_VERSION}-${DEBIAN_VERSION} AS builder

# Re-declare ARGs after FROM to use them in this stage
ARG NODEJS_VERSION

RUN --mount=type=cache,target=/root/.cache/pip,id=pip-cache \
    pip install uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# RUN --mount=type=cache,sharing=locked,target=/etc/apt/sources.list.d/  \
RUN sed -i s/http/https/g /etc/apt/sources.list.d/debian.sources

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=apt-cache \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked,id=apt-lists \
    apt update && \
    apt install -y libsasl2-dev python-dev-is-python3 libldap2-dev libssl-dev curl gettext && \
    curl -fsSL https://deb.nodesource.com/setup_${NODEJS_VERSION}.x | bash - && \
    apt-get install -y nodejs

WORKDIR /app

COPY pyproject.toml uv.lock yarn.lock package.json ./

RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv sync --frozen --all-extras --no-extra=dev --no-install-project

RUN --mount=type=cache,target=/root/.npm,id=npm-cache \
    --mount=type=cache,target=/root/.yarn,id=yarn-cache \
    npx yarn install --dev --ignore-optional && \
    npx yarn add grunt

COPY . .

RUN npx grunt build-non-interactive

RUN rm -rf node_modules

RUN --mount=type=cache,target=/root/.npm,id=npm-cache \
    --mount=type=cache,target=/root/.yarn,id=yarn-cache \
    npx yarn install --prod


RUN uv run src/manage.py compilemessages -v0 -l pl --traceback


RUN find .venv -type f -name "*.pyc" -delete && \
    python -m compileall -j 0 .venv -x 'wsgiutils' || true

##########################################################################################

# Re-declare for runtime stage
ARG PYTHON_VERSION
ARG DEBIAN_VERSION
FROM python:${PYTHON_VERSION}-slim-${DEBIAN_VERSION} AS runtime

RUN sed -i s/http/https/g /etc/apt/sources.list.d/debian.sources

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=apt-cache \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked,id=apt-lists \
    --mount=type=cache,target=/root/.cache/pip,id=pip-cache \
    pip install uv && \
    apt update && \
    apt install -y python3-pip libpango-1.0-0 libpangoft2-1.0-0 postgresql-client pandoc curl fonts-dejavu procps

ENV PATH="/.venv/bin:$PATH" \
    PYTHONPATH=/src \
    DJANGO_SETTINGS_MODULE=django_bpp.settings.production

WORKDIR /app

COPY --from=builder /app/node_modules ./node_modules

COPY --from=builder /app/.venv ./.venv

COPY --from=builder /app/src ./src
