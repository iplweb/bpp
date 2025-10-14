##########################################################################################

FROM python:3.12-trixie AS builder

RUN pip install uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# RUN --mount=type=cache,sharing=locked,target=/etc/apt/sources.list.d/  \
RUN sed -i s/http/https/g /etc/apt/sources.list.d/debian.sources

# RUN --mount=type=cache,sharing=locked,target=/var/cache/apt  \
RUN apt update && \
    apt install -y libsasl2-dev python-dev-is-python3 libldap2-dev libssl-dev curl gettext && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock yarn.lock package.json ./

RUN uv sync --frozen --all-extras --no-extra=dev --no-install-project

RUN npx yarn install --dev --ignore-optional

RUN npx yarn add grunt

COPY . .

RUN npx grunt build-non-interactive

RUN rm -rf node_modules

RUN npx yarn install --prod

RUN uv run src/manage.py compilemessages -v0 --traceback

RUN uv cache clean

RUN uv cache prune

##########################################################################################

FROM python:3.12-slim-trixie AS runtime

RUN sed -i s/http/https/g /etc/apt/sources.list.d/debian.sources

RUN pip install uv && \
    apt update && \
    apt install -y python3-pip libpango-1.0-0 libpangoft2-1.0-0 postgresql-client pandoc curl  && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/.venv/bin:$PATH" \
    PYTHONPATH=/src

COPY --from=builder /app/node_modules ./node_modules

COPY --from=builder /app/.venv /.venv

COPY --from=builder /app/src /src
