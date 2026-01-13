# Lightweight auth server for nginx authentication
# Uses the same base image but with minimal startup (no migrations, no collectstatic)

FROM iplweb/bpp_base:latest

# Install gunicorn for WSGI serving (not in base image dependencies)
RUN uv pip install gunicorn

# Install netcat for Redis connectivity check in entrypoint
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=apt-cache \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked,id=apt-lists \
    apt-get update && \
    apt-get install -y --no-install-recommends netcat-openbsd

EXPOSE 8001

COPY --chmod=755 deploy/authserver/entrypoint-authserver.sh /

# Fast health check - auth server should start in seconds
HEALTHCHECK --interval=5s --timeout=3s --retries=3 --start-period=10s \
    CMD curl --fail --silent http://127.0.0.1:8001/health/ || exit 1

ENTRYPOINT ["/bin/bash", "-c", "/entrypoint-authserver.sh"]
