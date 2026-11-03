"""Ustawienie tokenu PBN użytkownika z wiersza poleceń.

Wymienia jednorazowy ``ott`` (z adresu callbacku PBN) na token — tą samą
ścieżką co widok ``/pbn_api/callback`` — albo ustawia gotowy token
(``--token``) bez kontaktu z PBN. Nie sprawdza sesji ani oczekującej
autoryzacji: uruchomienie wymaga dostępu do shella serwera.
"""

import requests
from django.core.management import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from bpp.models import BppUser, Uczelnia
from pbn_api.autoryzacja import zapisz_token, zapisz_token_z_ott
from pbn_api.exceptions import (
    AuthenticationConfigurationError,
    AuthenticationResponseError,
)


def _znajdz_uczelnie(wartosc):
    if wartosc:
        qs = Uczelnia.objects.all()
        uczelnia = None
        if wartosc.isdigit():
            uczelnia = qs.filter(pk=int(wartosc)).first()
        if uczelnia is None:
            uczelnia = qs.filter(skrot=wartosc).first()
        if uczelnia is None:
            raise CommandError(f"Nie znaleziono uczelni o ID lub skrócie {wartosc!r}.")
        return uczelnia

    uczelnie = list(Uczelnia.objects.order_by("pk"))
    if not uczelnie:
        raise CommandError("W systemie nie ma żadnej uczelni.")
    if len(uczelnie) > 1:
        lista = ", ".join(f"{u.pk} ({u.skrot})" for u in uczelnie)
        raise CommandError(
            f"W systemie jest kilka uczelni - wskaż jedną przez --uczelnia "
            f"<ID|skrót>. Dostępne: {lista}"
        )
    return uczelnie[0]


class Command(BaseCommand):
    help = (
        "Zamienia jednorazowy kod OTT z PBN na token PBN użytkownika i zapisuje "
        "go (jak callback /pbn_api/callback), albo ustawia gotowy token "
        "podany przez --token."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "ott",
            nargs="?",
            default=None,
            help="Jednorazowy kod OTT z adresu callbacku PBN (?ott=...).",
        )
        parser.add_argument(
            "--user",
            required=True,
            help="Login użytkownika BPP, któremu zapisać token.",
        )
        parser.add_argument(
            "--uczelnia",
            default=None,
            help=(
                "ID lub skrót uczelni (konfiguracja PBN). Domyślnie jedyna "
                "uczelnia w systemie."
            ),
        )
        parser.add_argument(
            "--token",
            default=None,
            help=(
                "Ustaw podany token PBN bez kontaktu z PBN (np. przeniesiony "
                "z innego serwera). Wyklucza się z OTT."
            ),
        )
        parser.add_argument(
            "--pokaz-token",
            action="store_true",
            help=(
                "UWAGA: wypisuje token PBN na stdout. Token jest SEKRETEM "
                "(daje dostęp do PBN w imieniu użytkownika) - nie wklejaj go "
                "do logów, zgłoszeń ani czatów."
            ),
        )

    def handle(self, *args, ott=None, user=None, uczelnia=None, token=None, **kw):
        if ott and token:
            raise CommandError("Podaj albo OTT, albo --token - nie oba naraz.")
        if not ott and not token:
            raise CommandError("Podaj OTT (argument pozycyjny) albo --token.")

        try:
            bpp_user = BppUser.objects.get(username=user)
        except BppUser.DoesNotExist as e:
            raise CommandError(f"Nie ma użytkownika o loginie {user!r}.") from e

        with transaction.atomic():
            if token:
                zapisz_token(bpp_user, token)
                wynik = token
            else:
                ucz = _znajdz_uczelnie(uczelnia)
                try:
                    wynik = zapisz_token_z_ott(bpp_user, ucz, ott)
                except AuthenticationConfigurationError as e:
                    raise CommandError(f"Błąd konfiguracji autoryzacji PBN: {e}") from e
                except AuthenticationResponseError as e:
                    raise CommandError(
                        "PBN odrzucił kod OTT (nieprawidłowy, wygasły albo "
                        "już użyty) lub zwrócił błędną odpowiedź."
                    ) from e
                except requests.RequestException as e:
                    raise CommandError(
                        f"Nie udało się połączyć z PBN ({ucz.pbn_api_root}): {e}"
                    ) from e

        bpp_user.refresh_from_db()
        kiedy = timezone.localtime(bpp_user.pbn_token_updated)
        self.stdout.write(
            self.style.SUCCESS(
                f"Zapisano token PBN dla użytkownika {bpp_user.username} "
                f"({kiedy:%Y-%m-%d %H:%M:%S})."
            )
        )
        if kw.get("pokaz_token"):
            self.stdout.write(wynik)
