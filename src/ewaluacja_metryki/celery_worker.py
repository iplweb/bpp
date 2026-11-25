"""Sprawdzenie, czy działa choć jeden worker Celery.

Używane przy anulowaniu generowania metryk, które nie wystartowało
(``StatusGenerowania.anuluj_jesli_nie_wystartowalo``) — żeby powiedzieć
użytkownikowi wprost, że usługa przetwarzania w tle nie działa, zamiast
kazać mu próbować w kółko.
"""

import logging

from kombu.exceptions import OperationalError
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

#: Ile sekund czekamy na odpowiedź workerów na ``ping``. Żądanie HTTP czeka
#: tyle w całości, więc ma być krótko; wołane raz na anulowany przebieg.
LIMIT_ODPOWIEDZI_WORKERA_SEKUNDY = 2.0


def czy_dziala_worker_celery(timeout=LIMIT_ODPOWIEDZI_WORKERA_SEKUNDY):
    """``True`` — odpowiedział co najmniej jeden worker, ``False`` — żaden,
    ``None`` — nie wiadomo (nie udało się zapytać, np. broker niedostępny).
    """
    from django_bpp.celery_tasks import app

    try:
        odpowiedzi = app.control.inspect(timeout=timeout).ping()
    except (OperationalError, RedisError, OSError):
        # Broker niedostępny / zerwane połączenie: strona statusu ma działać
        # dalej, a o samym workerze nic nie wiemy.
        logger.exception("Nie udało się sprawdzić, czy działa worker Celery")
        return None
    return bool(odpowiedzi)
