"""Management command: create_demo_data.

Thin entrypoint — caly logika siedzi w bpp.demo_data.orchestrator.
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

from django.core.management.base import BaseCommand

from bpp.demo_data.orchestrator import CreateOptions, run_create


class Command(BaseCommand):
    help = (
        "Generuje syntetyczne dane demo (wydzialy, jednostki, autorzy, "
        "prace WC+WZ). Wymaga PODWOJNEGO potwierdzenia interaktywnie "
        "(prompt + exact DB name) lub flag --yes-i-am-sure + --confirm-db."
    )

    def add_arguments(self, parser):
        parser.add_argument("--wydzialow", type=int, default=10)
        parser.add_argument("--jednostek-na-wydzial", type=int, default=5)
        parser.add_argument("--autorow", type=int, default=500)
        parser.add_argument("--ile-ciaglych", type=int, default=5000)
        parser.add_argument("--ile-zwartych", type=int, default=5000)
        parser.add_argument("--od-roku", type=int, default=2017)
        parser.add_argument("--do-roku", type=int, default=2025)
        parser.add_argument("--procent-z-dyscyplina", type=int, default=80)
        parser.add_argument("--procent-z-subdyscyplina", type=int, default=20)
        parser.add_argument("--procent-zmiana-dyscypliny", type=int, default=10)
        parser.add_argument("--zrodel", type=int, default=50)
        parser.add_argument("--wydawcow", type=int, default=20)
        parser.add_argument("--seed", type=int, default=None)
        parser.add_argument("--manifest-out", type=str, default=None)
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--yes-i-am-sure", action="store_true")
        parser.add_argument("--confirm-db", type=str, default=None)

    def handle(self, *args, **options):
        manifest_out = options.get("manifest_out")
        if not manifest_out:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            manifest_out = f"demo_data_manifest_{ts}.json"

        opts = CreateOptions(
            wydzialow=options["wydzialow"],
            jednostek_na_wydzial=options["jednostek_na_wydzial"],
            autorow=options["autorow"],
            ile_ciaglych=options["ile_ciaglych"],
            ile_zwartych=options["ile_zwartych"],
            od_roku=options["od_roku"],
            do_roku=options["do_roku"],
            procent_z_dyscyplina=options["procent_z_dyscyplina"],
            procent_z_subdyscyplina=options["procent_z_subdyscyplina"],
            procent_zmiana_dyscypliny=options["procent_zmiana_dyscypliny"],
            zrodel=options["zrodel"],
            wydawcow=options["wydawcow"],
            seed=options["seed"],
            manifest_out=Path(manifest_out),
            batch_size=options["batch_size"],
            yes_i_am_sure=options["yes_i_am_sure"],
            confirm_db=options.get("confirm_db"),
        )
        # BaseCommand ma self.stdout (OutputWrapper) ale NIE ma self.stdin —
        # passujemy sys.stdin explicit (potrzebne dla double_confirm w trybie
        # interaktywnym / dla detekcji non-tty w trybie agentskim).
        run_create(opts, stdin=sys.stdin, stdout=self.stdout)
