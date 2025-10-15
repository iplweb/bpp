FROM iplweb/bpp_base:latest

ENTRYPOINT ["uv", "run", "celery", "-A", "django_bpp.celery_tasks"]

HEALTHCHECK --interval=10s --timeout=10s --start-period=5s --retries=5 CMD ["/bin/sh", "-c", "uv run celery -A django_bpp.celery_tasks inspect ping --destination celery@$HOSTNAME"]
