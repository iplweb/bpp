"""Settings do benchmarku ORM-a (Django 5.2 vs 6.1) na produkcyjnym dumpie.

Używany przez skrypty w ``bench/``. Konfiguracja DEV-ONLY — nie ładuje
się w produkcji (dziedziczy po ``local.py``). Porty i hasła da się nadpisać
przez zmienne środowiskowe (``os.environ.setdefault`` niżej).

Celowe odstępstwa od ``local.py``, każde po to, żeby pomiar mierzył PRACĘ
ORM-a, a nie coś obok:

* ``easyaudit`` — WYCISZONY, ale NIE usunięty z ``INSTALLED_APPS``.
  Middleware dokłada INSERT do każdego requestu (produkcja go nie ma,
  jest tylko w ``local.py``) i przesłoniłby różnicę w SELECT-ach szumem
  z zapisów, więc middleware + hooki sygnałów gasimy. Samej APLIKACJI
  ruszyć nie można: ``bpp.0470_indeksy_gin_i_funkcyjne`` deklaruje
  zależność od ``easyaudit.0001_initial``, więc bez niej graf migracji
  nie daje się zbudować (``NodeNotFoundError``).
* ``constance_cache`` zostaje na Redisie (własny kontener na 55379, nie
  cudzy dev-owy 6379). LocMem tu NIE przejdzie: ``constance`` jawnie
  odrzuca lokalny backend (``ImproperlyConfigured``: „refers to a
  subclass of Django's local-memory backend … set it to a backend that
  supports cross-process caching"). ``CACHES["default"]`` pozostaje
  DummyCache z ``local.py`` — i tak ma zostać: wyłączony cache aplikacji
  = widać całą pracę bazy, po obu stronach jednakowo.
* ``CONN_MAX_AGE = 0`` — świeże połączenie, bez efektów cieplnych puli.
"""

import os

os.environ.setdefault("DJANGO_BPP_SKIP_DOTENV", "1")
os.environ.setdefault("DJANGO_BPP_DB_HOST", "localhost")
os.environ.setdefault("DJANGO_BPP_DB_PORT", "55432")
os.environ.setdefault("DJANGO_BPP_DB_NAME", "bpp")
os.environ.setdefault("DJANGO_BPP_DB_USER", "bpp")
os.environ.setdefault("DJANGO_BPP_DB_PASSWORD", "password")
os.environ.setdefault("DJANGO_BPP_REDIS_PORT", "55379")

from .local import *  # noqa
from .local import CACHES, DATABASES, INSTALLED_APPS, MIDDLEWARE  # noqa

DEBUG = False
ALLOWED_HOSTS = ["*"]

MIDDLEWARE[:] = [m for m in MIDDLEWARE if "easyaudit" not in m]
DJANGO_EASY_AUDIT_WATCH_MODEL_EVENTS = False
DJANGO_EASY_AUDIT_WATCH_AUTH_EVENTS = False
DJANGO_EASY_AUDIT_WATCH_REQUEST_EVENTS = False

CACHES["constance_cache"] = {
    "BACKEND": "django_redis.cache.RedisCache",
    "LOCATION": "redis://localhost:55379/8",
}

DATABASES["default"]["CONN_MAX_AGE"] = 0
