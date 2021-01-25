# -*- encoding: utf-8 -*-

from celery import Celery, signals
from django.conf import settings


@signals.setup_logging.connect
def setup_logging(**kwargs):
    """Setup logging."""


class Celery(Celery):
    def on_configure(self):
        if hasattr(settings, "RAVEN_CONFIG") and settings.RAVEN_CONFIG["dsn"]:
            import raven
            from raven.contrib.celery import register_logger_signal, register_signal

            client = raven.Client(settings.RAVEN_CONFIG["dsn"])
            register_logger_signal(client)
            register_signal(client)


app = Celery("django_bpp")
app.config_from_object("django.conf:settings")
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
