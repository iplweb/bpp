import os
import shlex
import subprocess
import time

import psutil
import pytest

from bpp.tasks import remove_old_report_files


@pytest.mark.django_db
def test_celery(settings):
    # UWAGA UWAGA UWAGA
    # Po co ten test? Ano po to, żeby sprawdzić, czy workera da się
    # w ogóle uruchomić i czy da mu się wysłać komunikat. Jakiś czas temu,
    # z uwagi na problemy z zależnościami (celery miało określone wymaganie
    # kombu>=4.0;<5; był bug w kombu).
    #
    # tl;dr: ten test sprawdza uruchamianie workera i wywoływanie zadań;

    from django.db import connection
    db_name = connection.settings_dict['NAME']

    my_env = os.environ.copy()
    my_env['DJANGO_BPP_DB_NAME'] = db_name

    cwd = os.path.abspath(
        os.path.join(os.path.dirname(__file__), ".."))

    # Start worker in background
    proc = subprocess.Popen(
        shlex.split("celery -A django_bpp.celery_tasks worker  --concurrency=1 -l info"),
        # Nie może być stdout/stderr, bo nie będzie uruchomiony w tle
        # stdout=subprocess.PIPE,
        # stderr=subprocess.PIPE,
        cwd=cwd, env=my_env)

    time.sleep(3)

    assert psutil.pid_exists(proc.pid), "worked failed to start"

    try:
        settings.CELERY_ALWAYS_EAGER = False
        remove_old_report_files.delay().wait(timeout=5)

    finally:
        # Kill the worker and wait for it
        proc.kill()
        proc.communicate()
        assert not psutil.pid_exists(proc.pid), "worker failed to quit"
