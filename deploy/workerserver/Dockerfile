FROM iplweb/bpp_base:latest

ENTRYPOINT ["celery", "-A", "django_bpp.celery_tasks"]

HEALTHCHECK --interval=10s --timeout=10s --start-period=5s --retries=5 CMD ["/bin/sh", "-c", "celery -A django_bpp.celery_tasks inspect ping --destination celery@$HOSTNAME"]
