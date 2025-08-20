FROM iplweb/bpp_base:latest

RUN python -mpip install flower

ENTRYPOINT ["celery", "-A", "django_bpp.celery_tasks", "flower"]
