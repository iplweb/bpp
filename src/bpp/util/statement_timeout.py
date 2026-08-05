"""Ogranicznik czasu pojedynczego zapytania (Postgres ``statement_timeout``).

``SET LOCAL`` żyje tylko w obrębie transakcji — całość owijamy w
``transaction.atomic()``, więc po wyjściu limit znika. Przekroczenie →
``OperationalError`` (łapane wyżej, np. zwracamy 503).
"""

from contextlib import contextmanager

from django.db import connection, transaction


@contextmanager
def statement_timeout(ms):
    with transaction.atomic():
        with connection.cursor() as c:
            c.execute("SET LOCAL statement_timeout = %s", [ms])
        yield
