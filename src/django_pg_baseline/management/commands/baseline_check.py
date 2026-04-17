"""CI gate: fail loudly when the baseline is too stale."""

from __future__ import annotations

import sys

from django.core.management.base import BaseCommand

from django_pg_baseline.conf import get_config
from django_pg_baseline.freshness import check_freshness


class Command(BaseCommand):
    help = "Check whether the baseline is still fresh enough."

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-delta",
            type=int,
            default=None,
            help="Override PG_BASELINE['FRESHNESS_MAX_DELTA'].",
        )

    def handle(self, *args, max_delta=None, **options):
        config = get_config()
        threshold = max_delta if max_delta is not None else config.freshness_max_delta
        try:
            report = check_freshness(threshold, config.meta_path)
        except FileNotFoundError as exc:
            self.stderr.write(str(exc))
            sys.exit(1)

        self.stdout.write(
            f"baseline git_sha    = {report.git_sha}\n"
            f"max-delta threshold = {report.max_delta}\n"
        )
        if report.ok:
            self.stdout.write(
                f"OK — largest delta is {report.worst_delta} migrations "
                f"in app '{report.worst_app}'."
            )
            return

        self.stdout.write("STALE — the following apps have too many new migrations:")
        for app, n in sorted(report.over.items(), key=lambda kv: -kv[1]):
            self.stdout.write(f"  {app}: +{n} new migrations since baseline")
        self.stdout.write(
            "\nRun `make rebuild-baseline`, commit the refreshed "
            f"{config.sql_path} + {config.meta_path}, push."
        )
        sys.exit(1)
