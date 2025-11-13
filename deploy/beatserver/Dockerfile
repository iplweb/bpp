FROM iplweb/bpp_base:latest

COPY entrypoint-beatserver.sh /app/entrypoint-beatserver.sh

ENTRYPOINT ["/app/entrypoint-beatserver.sh"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 CMD ["/bin/sh", "-c", "uv run celery -A django_bpp.celery_tasks inspect scheduled"]
