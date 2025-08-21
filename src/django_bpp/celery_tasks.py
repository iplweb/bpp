from celery import Celery
from celery.signals import worker_ready
from celery_singleton import clear_locks
from django.apps import apps
from django.conf import settings

app = Celery("django_bpp")
app.config_from_object("django.conf:settings")
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
app.autodiscover_tasks(lambda: [n.name for n in apps.get_app_configs()])


@worker_ready.connect
def unlock_all(**kwargs):
    clear_locks(app)
