"""Show a readable summary of the current baseline state."""

from __future__ import annotations

import json
import sys

from django.core.management.base import BaseCommand

from django_pg_baseline.conf import get_config
from django_pg_baseline.freshness import check_freshness


class Command(BaseCommand):
    help = "Print a summary of the baseline state and current delta."

    def handle(self, *args, **options):
        config = get_config()
        if not config.meta_path.exists():
            self.stderr.write(f"baseline.meta.json not found at {config.meta_path}")
            sys.exit(1)

        meta = json.loads(config.meta_path.read_text())
        self.stdout.write(f"git_sha:          {meta.get('git_sha')}")
        self.stdout.write(f"postgres_version: {meta.get('postgres_version')}")
        self.stdout.write(f"sql_path:         {config.sql_path}")
        self.stdout.write(f"meta_path:        {config.meta_path}")

        report = check_freshness(config.freshness_max_delta, config.meta_path)
        self.stdout.write(f"\nFreshness threshold: {config.freshness_max_delta}")
        self.stdout.write(
            f"Worst delta:         {report.worst_delta} ({report.worst_app})"
        )
        self.stdout.write("\nPer-app deltas (newer on disk than baseline):")
        for app, delta in sorted(report.deltas.items(), key=lambda kv: -kv[1]):
            flag = " !!!" if delta > config.freshness_max_delta else ""
            self.stdout.write(f"  {app:40s} +{delta}{flag}")
