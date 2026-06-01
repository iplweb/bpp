# Multi-stage build: get Docker CLI from official image
ARG BPP_BASE_TAG=latest
FROM docker:cli AS docker-cli

FROM iplweb/bpp_base:${BPP_BASE_TAG}

EXPOSE 8000

COPY --chmod=755 docker/appserver/entrypoint-appserver.sh /
COPY --chmod=644 docker/appserver/uvicorn_log_config.json /
COPY --chmod=644 docker/appserver/gunicorn_conf.py /gunicorn_appserver_conf.py

# Copy Docker CLI from official image (fast - ~5s vs ~70s apt install)
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker

ENTRYPOINT ["/bin/bash", "-c", "/entrypoint-appserver.sh"]
