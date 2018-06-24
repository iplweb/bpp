import os
import shlex
import subprocess
import time

import psutil

from bpp.tasks import remove_old_report_files


def test_celery(settings):

    # UWAGA UWAGA UWAGA
    # Worker uruchomiony w poniższy sposób korzysta z bazy danych "bpp",
    # nie zaś "test_bpp". Stąd, jezeli chcielibyśmy uruchamiać jakiekolwiek
    # testy i sprawdzać ich rezutlat, to to nie wyjdzie.
    # Po co zatem ten test? Ano po to, żeby sprawdzić, czy workera da się
    # w ogóle uruchomić i czy da mu się wysłać komunikat. Jakiś czas temu,
    # z uwagi na problemy z zależnościami (celery miało określone wymaganie
    # kombu>=4.0;<5; był bug w kombu).
    #
    # tl;dr: ten test sprawdza uruchamianie workera i wywoływanie zadań;
    # nie badaj zawartości bazy dancyh w przebiegu tego testu, bo worker
    # działa najprawdopodobniej na bazie danych "głównej", a ten test -
    # na testowej.

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
