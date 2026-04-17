"""Load ``baseline.sql`` into a Django-configured database."""

from __future__ import annotations

import sys

from django.core.management.base import BaseCommand
from django.db import connections

from django_pg_baseline.conf import get_config
from django_pg_baseline.loader import baseline_needed, load_baseline


class Command(BaseCommand):
    help = "Load baseline.sql into the configured database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            default=None,
            help="Database alias (defaults to PG_BASELINE['DATABASE_ALIAS']).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Load even when the database already has django_migrations.",
        )

    def handle(self, *args, database=None, force=False, **options):
        config = get_config()
        alias = database or config.database_alias
        dsn = connections[alias].settings_dict

        if not force:
            try:
                with connections[alias].cursor() as cur:
                    if not baseline_needed(cur):
                        self.stdout.write(
                            "Database is not empty — skipping baseline load "
                            "(use --force to override)."
                        )
                        return
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f"Could not probe database, loading anyway: {exc}")

        try:
            load_baseline(dsn, config.sql_path)
        except FileNotFoundError as exc:
            self.stderr.write(str(exc))
            sys.exit(1)
