import os
import platform

import rollbar
from celery import Celery
from celery.signals import task_failure, worker_ready
from celery_singleton import clear_locks
from django.apps import apps
from django.conf import settings

if platform.system() == "Darwin":
    os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

app = Celery("django_bpp")
app.config_from_object("django.conf:settings")
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
app.autodiscover_tasks(lambda: [n.name for n in apps.get_app_configs()])

# On macOS, prefork + C extensions (psycopg2, numpy, lxml, etc.) can segfault after fork.
# Default to threads locally unless explicitly overridden.
if platform.system() == "Darwin" and os.environ.get("CELERY_USE_PREFORK") != "1":
    app.conf.update(worker_pool="threads", worker_concurrency=10)


@worker_ready.connect
def unlock_all(**kwargs):
    clear_locks(app)


@worker_ready.connect
def initialize_rollbar(**kwargs):
    """Initialize Rollbar after Django settings are configured."""
    rollbar.init(**settings.ROLLBAR)
    rollbar.BASE_DATA_HOOK = celery_base_data_hook


@task_failure.connect
def handle_task_failure(**kw):
    rollbar.report_exc_info(extra_data=kw)


def celery_base_data_hook(request, data):
    data["framework"] = "celery"
    data["DJANGO_BPP_HOSTNAME"] = getattr(settings, "DJANGO_BPP_HOSTNAME", "None")
