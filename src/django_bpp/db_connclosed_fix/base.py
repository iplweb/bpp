import logging

import django.db
from django.db.backends.postgresql.base import (
    DatabaseWrapper as BuiltinPostgresDatabaseWrapper,
)
from psycopg2 import InterfaceError

logger = logging.getLogger(__name__)


class DatabaseWrapper(BuiltinPostgresDatabaseWrapper):
    def create_cursor(self, name=None):
        try:
            return super().create_cursor(name=name)
        except InterfaceError:
            # Reconnect tworzy NOWĄ sesję PostgreSQL — cały stan sesyjny
            # (tabele tymczasowe, advisory locks, SET) przepada. Logujemy
            # z traceback-iem, bo cicha podmiana sesji maskuje błędy typu
            # "relacja ... nie istnieje" na tabelach tymczasowych.
            logger.warning(
                "Polaczenie DB (alias=%s) bylo zamkniete przy tworzeniu "
                "kursora; przezroczysty reconnect — stan sesji PostgreSQL "
                "(temp tables, advisory locks) zostal utracony.",
                self.alias,
                exc_info=True,
            )
            django.db.close_old_connections()
            django.db.connection.connect()
            return super().create_cursor(name=name)
