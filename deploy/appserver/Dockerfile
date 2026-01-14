# Multi-stage build: get Docker CLI from official image
FROM docker:cli AS docker-cli

FROM iplweb/bpp_base:latest

EXPOSE 8000

COPY --chmod=755 deploy/appserver/entrypoint-appserver.sh /

# Copy Docker CLI from official image (fast - ~5s vs ~70s apt install)
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker

HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=1800s \
    CMD curl --fail --silent --write-out 'HTTP CODE : %{http_code}\n' --output /dev/null http://127.0.0.1:8000/

ENTRYPOINT ["/bin/bash", "-c", "/entrypoint-appserver.sh"]
