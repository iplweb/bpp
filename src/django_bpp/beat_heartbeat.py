"""Heartbeat-owy scheduler dla celerybeat -> tani healthcheck bez importu Django.

Domyslny PersistentScheduler nie daje zadnego sygnalu "beat zyje i tyka", a
poprzednia sonda (docker/beatserver/healthcheck_broker.py) cold-importowala caly
stack Django (config_from_object + autodiscover_tasks po calym INSTALLED_APPS) co
interval, tylko po to by otworzyc polaczenie do brokera. Pod limitem CPU kontenera
zajmowalo to 4-10 s i wydluzalo start celerybeat do ~218 s.

`HeartbeatScheduler` dotyka pliku-heartbeatu przy kazdym ticku, a sonda Dockera
(docker/beatserver/healthcheck_beat.py) sprawdza tylko swiezosc mtime tego pliku -
bez importu Django i bez sprawdzania redisa (redis ma wlasny healthcheck, a beat i
tak zalezy od redis: service_healthy, wiec ponowne sprawdzanie go z beata jest
redundantne). `tick()` jest dodatkowo capowany do HEARTBEAT_INTERVAL, zeby plik
odswiezal sie nawet gdy zadne zadanie nie jest bliskie (domyslny max_interval to 300 s).
"""

import logging
import pathlib

from celery.beat import PersistentScheduler

logger = logging.getLogger(__name__)

#: Plik dotykany przy kazdym ticku; healthcheck_beat.py sprawdza jego mtime.
#: Sciezka MUSI byc zgodna z HEARTBEAT_FILE w docker/beatserver/healthcheck_beat.py.
HEARTBEAT_FILE = pathlib.Path("/tmp/celerybeat-heartbeat")

#: Gorny limit snu petli beata (s) -> heartbeat odswieza sie co najwyzej co tyle,
#: nawet przy braku bliskich zadan. Sonda toleruje wiek do ~3x tej wartosci.
HEARTBEAT_INTERVAL = 30


def write_heartbeat(path):
    """Dotknij plik-heartbeat. Loguje i NIE wywraca beata gdy zapis sie nie uda.

    Zwraca True przy sukcesie, False przy bledzie I/O.
    """
    try:
        path.touch()
    except OSError as exc:
        logger.warning("celerybeat: nie udalo sie zapisac heartbeatu %s: %r", path, exc)
        return False
    return True


def cap_interval(interval, maximum=HEARTBEAT_INTERVAL):
    """Ogranicz sen petli beata, by heartbeat nie zestarzal sie przy braku zadan."""
    return min(interval, maximum)


class HeartbeatScheduler(PersistentScheduler):
    """PersistentScheduler dotykajacy pliku-heartbeatu na kazdym ticku."""

    def tick(self, *args, **kwargs):
        write_heartbeat(HEARTBEAT_FILE)
        return cap_interval(super().tick(*args, **kwargs))
