"""Wypisuje (JSON) obiekty danych demo pokazywane na zrzutach ekranu.

Używa go ``bin/docs-screenshots.py``: scenariusze działają w Playwright, poza
ORM, więc identyfikatory, nazwy i adresy obiektów dostają z tego polecenia.
Reguły wyboru: ``bpp.demo_data.zrzuty``.
"""

import json

from django.core.management.base import BaseCommand

from bpp.demo_data.zrzuty import obiekty


class Command(BaseCommand):
    help = "Wypisuje JSON z obiektami danych demo dla bin/docs-screenshots.py"

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(obiekty(), ensure_ascii=False, indent=2))
