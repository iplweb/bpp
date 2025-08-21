FROM iplweb/bpp_base:latest

ENTRYPOINT ["celery", "-A", "django_bpp.celery_tasks", "beat", "--pidfile=/celerybeat.pid", "-s", "/celerybeat-schedule"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 CMD ["/bin/sh", "-c", "celery -A django_bpp.celery_tasks inspect scheduled"]
