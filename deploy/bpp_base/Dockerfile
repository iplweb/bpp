##########################################################################################

FROM python:3.12-trixie AS builder

RUN pip install uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# RUN --mount=type=cache,sharing=locked,target=/etc/apt/sources.list.d/  \
RUN sed -i s/http/https/g /etc/apt/sources.list.d/debian.sources

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt update && \
    apt install -y libsasl2-dev python-dev-is-python3 libldap2-dev libssl-dev curl gettext && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

WORKDIR /app

COPY pyproject.toml uv.lock yarn.lock package.json ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --all-extras --no-extra=dev --no-install-project

RUN --mount=type=cache,target=/root/.npm \
    --mount=type=cache,target=/root/.yarn \
    npx yarn install --dev --ignore-optional

RUN --mount=type=cache,target=/root/.npm \
    --mount=type=cache,target=/root/.yarn \
    npx yarn add grunt

COPY . .

RUN npx grunt build-non-interactive

RUN rm -rf node_modules

RUN --mount=type=cache,target=/root/.npm \
    --mount=type=cache,target=/root/.yarn \
    npx yarn install --prod


RUN uv run src/manage.py compilemessages -v0 -l pl --traceback

##########################################################################################

FROM python:3.12-slim-trixie AS runtime

RUN sed -i s/http/https/g /etc/apt/sources.list.d/debian.sources

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    pip install uv && \
    apt update && \
    apt install -y python3-pip libpango-1.0-0 libpangoft2-1.0-0 postgresql-client pandoc curl fonts-dejavu

ENV PATH="/.venv/bin:$PATH" \
    PYTHONPATH=/src \
    DJANGO_SETTINGS_MODULE=django_bpp.settings.production

WORKDIR /app

COPY --from=builder /app/node_modules ./node_modules

COPY --from=builder /app/.venv ./.venv

COPY --from=builder /app/src ./src
