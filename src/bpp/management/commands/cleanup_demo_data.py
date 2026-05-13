"""Management command: cleanup_demo_data.

Thin entrypoint — caly logika siedzi w bpp.demo_data.orchestrator.
"""

from __future__ import annotations

import sys
from pathlib import Path

from django.core.management.base import BaseCommand

from bpp.demo_data.orchestrator import CleanupOptions, run_cleanup


class Command(BaseCommand):
    help = (
        "Usuwa obiekty zapisane w manifescie stworzonym przez "
        "create_demo_data. Wymaga podwojnego potwierdzenia jak komenda "
        "tworzaca."
    )

    def add_arguments(self, parser):
        parser.add_argument("--manifest", type=str, required=True)
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--yes-i-am-sure", action="store_true")
        parser.add_argument("--confirm-db", type=str, default=None)

    def handle(self, *args, **options):
        opts = CleanupOptions(
            manifest=Path(options["manifest"]),
            yes_i_am_sure=options["yes_i_am_sure"],
            confirm_db=options.get("confirm_db"),
            batch_size=options["batch_size"],
        )
        run_cleanup(opts, stdin=sys.stdin, stdout=self.stdout)
