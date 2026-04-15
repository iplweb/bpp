"""Regenerate ``baseline.sql`` + ``baseline.meta.json`` via testcontainers."""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand

from django_pg_baseline.conf import get_config
from django_pg_baseline.rebuild import rebuild_baseline


class Command(BaseCommand):
    help = "Regenerate baseline.sql and baseline.meta.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "--image",
            default=None,
            help="Override PG_BASELINE['REBUILD_IMAGE'].",
        )
        parser.add_argument(
            "--baseline-dir",
            default=None,
            help="Override PG_BASELINE['BASELINE_DIR'].",
        )

    def handle(self, *args, image=None, baseline_dir=None, **options):
        config = get_config()
        if image:
            config.rebuild_image = image
        if baseline_dir:
            config.baseline_dir = Path(baseline_dir)

        self.stdout.write(f"Rebuilding baseline using image {config.rebuild_image}...")
        rebuild_baseline(config)
        self.stdout.write(self.style.SUCCESS("Baseline rebuilt."))
        self.stdout.write(f"  sql:  {config.sql_path}")
        self.stdout.write(f"  meta: {config.meta_path}")
