ARG BPP_BASE_TAG=latest

FROM iplweb/bpp_base:${BPP_BASE_TAG}

EXPOSE 8000

COPY --chmod=755 docker/appserver/entrypoint-appserver.sh /
COPY --chmod=644 docker/appserver/uvicorn_log_config.json /
COPY --chmod=644 docker/appserver/gunicorn_conf.py /gunicorn_appserver_conf.py

# Docker CLI celowo NIE jest instalowany: konwersja DOCX (html2docx) idzie
# teraz przez usługę HTTP (DJANGO_BPP_HTML2DOCX_URL), a nie przez docker.sock.
# Dzięki temu appserver nie ma dostępu do demona Dockera hosta.

ENTRYPOINT ["/bin/bash", "-c", "/entrypoint-appserver.sh"]
