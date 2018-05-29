import os
import shlex
import subprocess
import time

import psutil

from bpp.tasks import remove_old_report_files


def test_celery(settings):
    cwd = os.path.abspath(
        os.path.join(os.path.dirname(__file__), ".."))

    # Start worker in background
    proc = subprocess.Popen(
        shlex.split("celery -A django_bpp.celery_tasks worker  --concurrency=1 -l info"),
        # Nie może być stdout/stderr, bo nie będzie uruchomiony w tle
        # stdout=subprocess.PIPE,
        # stderr=subprocess.PIPE,
        cwd=cwd)

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
