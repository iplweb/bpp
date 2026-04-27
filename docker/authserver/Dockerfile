# Lightweight auth server for nginx authentication
# Uses the same base image but with minimal startup (no migrations, no collectstatic)

ARG BPP_BASE_TAG=latest
FROM iplweb/bpp_base:${BPP_BASE_TAG}

# gunicorn jest instalowany jako główna zależność w pyproject.toml,
# więc tu tylko doinstalujemy netcat do sprawdzania Redisa.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=apt-cache \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked,id=apt-lists \
    apt-get update && \
    apt-get install -y --no-install-recommends netcat-openbsd

EXPOSE 8001

COPY --chmod=755 docker/authserver/entrypoint-authserver.sh /
COPY --chmod=644 docker/authserver/gunicorn_conf.py /

ENTRYPOINT ["/bin/bash", "-c", "/entrypoint-authserver.sh"]
