FROM iplweb/bpp_base:latest

RUN --mount=type=cache,target=/root/.cache/pip \
    python -mpip install flower

ENTRYPOINT ["celery", "-A", "django_bpp.celery_tasks", "flower"]
