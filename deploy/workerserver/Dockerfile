FROM iplweb/bpp_base:latest

COPY deploy/workerserver/entrypoint-workerserver.sh /app/entrypoint-workerserver.sh

ENTRYPOINT ["/app/entrypoint-workerserver.sh"]

HEALTHCHECK --interval=10s --timeout=10s --start-period=35s --retries=5 CMD ["/bin/sh", "-c", "uv run celery -A django_bpp.celery_tasks inspect ping --destination celery@$HOSTNAME"]
