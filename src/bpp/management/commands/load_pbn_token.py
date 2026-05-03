"""Wczytaj token PBN użytkownika z JSON-a na stdin.

Druga połowa pary z `dump_pbn_token`. Czyta JSON wyprodukowany przez
`dump_pbn_token` ze stdin i ustawia pola pbn_token / pbn_token_updated
na lokalnym użytkowniku.

    ssh prod "uv run python src/manage.py dump_pbn_token --user=foo" \\
        | uv run python src/manage.py load_pbn_token --user=foo
"""

import json
import sys

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime


class Command(BaseCommand):
    help = (
        "Wczytaj token PBN ze stdin (JSON z dump_pbn_token) i przypisz go "
        "wskazanemu użytkownikowi."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            help=(
                "username lokalnego użytkownika BppUser, któremu ustawić token. "
                "Jeśli nie podany, użyty zostanie username z payloadu."
            ),
        )
        parser.add_argument(
            "--from-file",
            help="Wczytaj JSON z pliku zamiast ze stdin.",
        )

    def handle(self, *args, **options):
        if options["from_file"]:
            with open(options["from_file"]) as f:
                raw = f.read()
        else:
            raw = sys.stdin.read()

        if not raw.strip():
            raise CommandError("Brak danych na wejściu (pusty stdin / plik).")

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            raise CommandError(f"Nieprawidłowy JSON na wejściu: {e}") from e

        for key in ("username", "pbn_token", "pbn_token_updated"):
            if key not in payload:
                raise CommandError(
                    f"Brakujące pole {key!r} w payloadzie. Czy źródłem był "
                    "dump_pbn_token?"
                )

        username = options["user"] or payload["username"]
        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as e:
            raise CommandError(f"Lokalny użytkownik {username!r} nie istnieje") from e

        updated_raw = payload["pbn_token_updated"]
        if updated_raw is None:
            updated = None
        else:
            updated = parse_datetime(updated_raw)
            if updated is None:
                raise CommandError(
                    f"Nie udało się sparsować pbn_token_updated={updated_raw!r}"
                )

        user.pbn_token = payload["pbn_token"]
        user.pbn_token_updated = updated
        user.save(update_fields=["pbn_token", "pbn_token_updated"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Ustawiono pbn_token dla {user.username} "
                f"(updated={updated.isoformat() if updated else 'None'})"
            )
        )
