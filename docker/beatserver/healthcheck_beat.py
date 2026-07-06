"""Lekki healthcheck celerybeat: swiezosc pliku-heartbeatu (bez importu Django).

Beat dziala z HeartbeatScheduler (src/django_bpp/beat_heartbeat.py), ktory dotyka
HEARTBEAT_FILE przy kazdym ticku. Ten skrypt tylko sprawdza, czy plik jest swiezy -
bez importu django_bpp.celery_tasks i bez laczenia z brokerem (redis ma wlasny
healthcheck). Dzieki temu sonda trwa ~30-50 ms zamiast 4-10 s (cold-import calego
stacku), wiec nie wydluza startu kontenera ani nie obciaza limitu CPU beata.

Celowo bez zaleznosci poza stdlib - import celery/Django zniwelowalby cala oszczednosc.
"""

import os
import sys
import time

#: MUSI byc zgodne z HEARTBEAT_FILE w src/django_bpp/beat_heartbeat.py.
HEARTBEAT_FILE = "/tmp/celerybeat-heartbeat"

#: Maks. akceptowalny wiek heartbeatu. > 2x HEARTBEAT_INTERVAL (30 s) = zapas na
#: wariancje petli beata; ponizej tego beat na pewno tyka.
MAX_AGE_SECONDS = 90


def main() -> int:
    try:
        age = time.time() - os.path.getmtime(HEARTBEAT_FILE)
    except OSError as exc:
        print(
            f"celerybeat: brak/niedostepny heartbeat {HEARTBEAT_FILE}: {exc!r}",
            file=sys.stderr,
        )
        return 1

    if age > MAX_AGE_SECONDS:
        print(
            f"celerybeat: heartbeat przestarzaly ({age:.0f}s > {MAX_AGE_SECONDS}s) "
            "- beat moze nie tykac",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
