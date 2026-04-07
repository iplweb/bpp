# Lightweight auth server for nginx authentication
# Uses the same base image but with minimal startup (no migrations, no collectstatic)

ARG BPP_BASE_TAG=latest
FROM iplweb/bpp_base:${BPP_BASE_TAG}

# Install gunicorn + netcat (for Redis connectivity check)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=apt-cache \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked,id=apt-lists \
    apt-get update && \
    apt-get install -y --no-install-recommends netcat-openbsd && \
    uv pip install gunicorn

EXPOSE 8001

COPY --chmod=755 docker/authserver/entrypoint-authserver.sh /

# Fast health check - auth server should start in seconds
HEALTHCHECK --interval=5s --timeout=3s --retries=3 --start-period=10s \
    CMD curl --fail --silent http://127.0.0.1:8001/health/ || exit 1

ENTRYPOINT ["/bin/bash", "-c", "/entrypoint-authserver.sh"]
