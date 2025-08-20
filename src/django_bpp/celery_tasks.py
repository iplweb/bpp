from celery import Celery
from django.apps import apps
from django.conf import settings

app = Celery("django_bpp")
app.config_from_object("django.conf:settings")
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
app.autodiscover_tasks(lambda: [n.name for n in apps.get_app_configs()])
