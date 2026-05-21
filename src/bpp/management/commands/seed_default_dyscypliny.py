"""Management command: seed_default_dyscypliny."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from bpp.demo_data.default_dyscypliny import (
    DEFAULT_DYSCYPLINY,
    seed_default_dyscypliny,
)


class Command(BaseCommand):
    help = (
        f"Wstawia domyslny slownik {len(DEFAULT_DYSCYPLINY)} dyscyplin "
        "naukowych zgodnie z Rozporzadzeniem MEiN z 11.10.2022. "
        "Idempotentne: get_or_create po kodzie. Pomija dziedziny 9 "
        "(o rodzinie) i 10 (weterynaryjne) — bpp.const.DZIEDZINY ich "
        "nie zawiera."
    )

    def handle(self, *args, **options):
        created, existed = seed_default_dyscypliny(stdout=self.stdout)
        self.stdout.write(
            f"[OK] Slownik dyscyplin: {created} nowych, {existed} istniejacych."
        )
