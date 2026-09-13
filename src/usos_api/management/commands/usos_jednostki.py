"""Pobiera strukturę jednostek uczelni z USOS API i wypisuje ją na ekran.

Komenda niczego nie zapisuje do bazy — to narzędzie rozpoznawcze, pozwalające
zobaczyć, co dana instalacja USOS-a w ogóle oddaje, zanim powstanie import.

Moduł ``fac`` działa anonimowo, więc to zadziała bez consumer key::

    uv run python src/manage.py usos_jednostki \\
        --base-url https://usosapps.umlub.pl/ --root 1000000000
"""

import json

from django.core.management.base import BaseCommand, CommandError

from usos_api.client import UsosApiError
from usos_api.conf import buduj_klienta
from usos_api.jednostki import pobierz_jednostki


class Command(BaseCommand):
    help = "Pobiera drzewo jednostek uczelni z USOS API (nie zapisuje do bazy)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--base-url",
            help="Adres instalacji USOS API; domyślnie USOS_API_BASE_URL z ustawień.",
        )
        parser.add_argument(
            "--root",
            required=True,
            help="Kod jednostki nadrzędnej, od której schodzimy w dół "
            "(np. 1000000000).",
        )
        parser.add_argument("--consumer-key")
        parser.add_argument("--consumer-secret")
        parser.add_argument(
            "--json",
            action="store_true",
            dest="jako_json",
            help="Wypisz surowy JSON zamiast drzewa.",
        )

    def handle(self, *args, **opcje):
        klient = buduj_klienta(
            base_url=opcje.get("base_url"),
            consumer_key=opcje.get("consumer_key"),
            consumer_secret=opcje.get("consumer_secret"),
        )

        try:
            jednostki = pobierz_jednostki(klient, opcje["root"])
        except UsosApiError as błąd:
            raise CommandError(f"USOS API odmówił: {błąd}") from błąd

        if opcje["jako_json"]:
            self.stdout.write(json.dumps(jednostki, indent=2, ensure_ascii=False))
            return

        for jednostka in jednostki:
            wcięcie = "  " * jednostka["poziom"]
            liczba = jednostka["liczba_pracownikow"]
            self.stdout.write(
                f"{jednostka['usos_id']}  {wcięcie}{jednostka['nazwa']} "
                f"[pracowników: {liczba}]"
            )

        self.stdout.write("")
        self.stdout.write(f"Razem jednostek: {len(jednostki)}")
