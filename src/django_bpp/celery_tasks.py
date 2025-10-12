import rollbar
from celery import Celery
from celery.signals import task_failure, worker_ready
from celery_singleton import clear_locks
from django.apps import apps
from django.conf import settings

if getattr(settings, "PYDANTIC_LOGFIRE_TOKEN", None):
    import logfire

    logfire.instrument_celery(exclude={"bpp-celery-denorm"})

app = Celery("django_bpp")
app.config_from_object("django.conf:settings")
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
app.autodiscover_tasks(lambda: [n.name for n in apps.get_app_configs()])


@worker_ready.connect
def unlock_all(**kwargs):
    clear_locks(app)


@task_failure.connect
def handle_task_failure(**kw):
    rollbar.report_exc_info(extra_data=kw)


def celery_base_data_hook(request, data):
    data["framework"] = "celery"


rollbar.init(**settings.ROLLBAR)
rollbar.BASE_DATA_HOOK = celery_base_data_hook
