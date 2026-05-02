"""Wypisz token PBN użytkownika jako JSON na stdout.

Pomyślane jako jedna połowa pary z `load_pbn_token`, do przenoszenia
sesji PBN ze zdalnego (produkcyjnego) serwera na lokalny dev przez SSH:

    ssh prod "uv run python src/manage.py dump_pbn_token --user=foo" \\
        | uv run python src/manage.py load_pbn_token --user=foo
"""

import json
import sys

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Wypisz token PBN wskazanego użytkownika jako JSON na stdout."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            required=True,
            help="username użytkownika BppUser, którego token chcemy wyeksportować",
        )
        parser.add_argument(
            "--allow-empty",
            action="store_true",
            help=(
                "Nie traktuj pustego/niezainicjalizowanego tokenu jako błąd. "
                "Bez tej flagi komenda kończy się błędem, gdy token jest pusty."
            ),
        )

    def handle(self, *args, **options):
        User = get_user_model()
        username = options["user"]

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as e:
            raise CommandError(f"Użytkownik {username!r} nie istnieje") from e

        if not user.pbn_token and not options["allow_empty"]:
            raise CommandError(
                f"Użytkownik {username!r} nie ma ustawionego tokenu PBN. "
                "Użyj --allow-empty, jeśli chcesz wyeksportować pusty token."
            )

        payload = {
            "username": user.username,
            "pbn_token": user.pbn_token,
            "pbn_token_updated": (
                user.pbn_token_updated.isoformat()
                if user.pbn_token_updated is not None
                else None
            ),
        }
        json.dump(payload, sys.stdout)
        sys.stdout.write("\n")
