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


def resolve_worker_config(environ, system, cpu_count):
    """Wyznacz konfigurację workera Celery na podstawie zmiennych środowiskowych.

    Czysta funkcja (bez side-effectów) — wszystkie wejścia przez argumenty,
    żeby dało się ją testować bez startu workera i bez mutowania os.environ.

    Zwraca dict gotowy do `app.conf.update(...)`. Opcjonalne knoby (prefetch,
    max_tasks/max_memory_per_child) trafiają do wyniku tylko gdy env ustawiony.
    """
    use_prefork_on_darwin = environ.get("CELERY_USE_PREFORK") == "1"
    is_darwin = system == "Darwin"
    default_pool = "threads" if (is_darwin and not use_prefork_on_darwin) else "prefork"
    pool = environ.get("CELERY_WORKER_POOL", default_pool)

    explicit = environ.get("CELERY_WORKER_CONCURRENCY")
    if explicit:
        concurrency = int(explicit)
    elif pool == "threads":
        # Dotychczasowy default deva (macOS): prefork + C-ext segfaultuje po forku.
        concurrency = 10
    else:
        percent = int(environ.get("CELERY_WORKER_CONCURRENCY_PERCENT", "75"))
        concurrency = max(1, round((cpu_count or 1) * percent / 100))

    config = {"worker_pool": pool, "worker_concurrency": concurrency}

    # Opcjonalne knoby — tylko gdy jawnie ustawione (puste = default Celery).
    optional = {
        "CELERY_WORKER_PREFETCH_MULTIPLIER": "worker_prefetch_multiplier",
        "CELERY_WORKER_MAX_TASKS_PER_CHILD": "worker_max_tasks_per_child",
        "CELERY_WORKER_MAX_MEMORY_PER_CHILD": "worker_max_memory_per_child",
    }
    for env_name, conf_key in optional.items():
        value = environ.get(env_name)
        if value:
            config[conf_key] = int(value)

    return config


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
    from bpp.rollbar_config import configure_rollbar

    configure_rollbar()
    # Keep the Celery-specific base data hook for framework identification
    rollbar.BASE_DATA_HOOK = celery_base_data_hook


@task_failure.connect
def handle_task_failure(**kw):
    rollbar.report_exc_info(extra_data=kw)


def celery_base_data_hook(request, data):
    """Add Celery framework identifier to Rollbar data.

    Note: DJANGO_BPP_HOSTNAME is now handled globally by the payload handler
    registered in bpp.rollbar_config.
    """
    data["framework"] = "celery"
