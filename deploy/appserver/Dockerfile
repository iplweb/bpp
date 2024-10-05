FROM iplweb/bpp_base:latest

EXPOSE 8000

COPY --chmod=755 deploy/appserver/entrypoint-appserver.sh /

RUN pip install uvicorn

HEALTHCHECK --interval=30s --timeout=5s --retries=4 --start-period=20s \
    CMD curl --fail --silent --write-out 'HTTP CODE : %{http_code}\n' --output /dev/null http://127.0.0.1:8000/

ENTRYPOINT ["/bin/bash", "-c", "/entrypoint-appserver.sh"]
