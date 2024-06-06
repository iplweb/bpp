FROM iplweb/bpp_base:latest

ENTRYPOINT ["/bin/bash", "-c", "celery -A django_bpp.celery_tasks worker"]
