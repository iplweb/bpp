ARG BPP_BASE_TAG=latest
FROM iplweb/bpp_base:${BPP_BASE_TAG}

COPY docker/beatserver/entrypoint-beatserver.sh /app/entrypoint-beatserver.sh

ENTRYPOINT ["/app/entrypoint-beatserver.sh"]

HEALTHCHECK --interval=10s --timeout=10s --start-period=40s --retries=3 CMD ["/bin/sh", "-c", "uv run celery -A django_bpp.celery_tasks inspect scheduled"]
