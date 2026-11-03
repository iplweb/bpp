"""Wymusza zmianę hasła przy najbliższym wejściu na stronę.

Dla każdego wybranego użytkownika zakłada wpis ``PasswordChangeRequired``
(django-password-policies). Middleware przekierowuje wtedy użytkownika do
formularza zmiany hasła, a zapis nowego hasła kasuje wpis. Przydatne po
podejrzeniu wycieku haseł albo żeby wszyscy przeszli na nową politykę haseł.

Obejmuje tylko aktywne konta z hasłem BPP (``has_usable_password``) — konta
zakładane wyłącznie przez Microsoft / ORCID hasła nie mają i nie są ruszane.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from password_policies.models import PasswordChangeRequired


class Command(BaseCommand):
    help = (
        "Wymusza zmianę hasła przy najbliższym wejściu na stronę wszystkim "
        "aktywnym użytkownikom logującym się hasłem BPP (albo tylko wskazanym "
        "loginom / członkom grup)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            action="append",
            default=[],
            help="Tylko ten login (można podać wiele razy).",
        )
        parser.add_argument(
            "--grupa",
            action="append",
            default=[],
            help="Tylko członkowie tej grupy (można podać wiele razy).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Pokaż, kogo by objęło, ale niczego nie zapisuj.",
        )

    def _wybierz(self, loginy, grupy):
        qs = get_user_model().objects.filter(is_active=True)

        if loginy:
            znalezione = set(
                qs.filter(username__in=loginy).values_list("username", flat=True)
            )
            brakujace = sorted(set(loginy) - znalezione)
            if brakujace:
                raise CommandError(
                    "Brak aktywnych użytkowników: " + ", ".join(brakujace)
                )
            qs = qs.filter(username__in=loginy)

        if grupy:
            znalezione = set(
                Group.objects.filter(name__in=grupy).values_list("name", flat=True)
            )
            brakujace = sorted(set(grupy) - znalezione)
            if brakujace:
                raise CommandError("Brak grup: " + ", ".join(brakujace))
            qs = qs.filter(groups__name__in=grupy).distinct()

        # has_usable_password() to metoda, nie pole -- filtr w Pythonie.
        return [u for u in qs.order_by("username") if u.has_usable_password()]

    @transaction.atomic
    def handle(self, *args, **options):
        uzytkownicy = self._wybierz(options["username"], options["grupa"])
        juz_wymuszeni = set(
            PasswordChangeRequired.objects.filter(user__in=uzytkownicy).values_list(
                "user_id", flat=True
            )
        )
        nowi = [u for u in uzytkownicy if u.pk not in juz_wymuszeni]

        if options["dry_run"]:
            for user in nowi:
                self.stdout.write(user.username)
            self.stdout.write(
                f"[dry-run] Zmiana hasła zostałaby wymuszona dla {len(nowi)} "
                f"użytkowników ({len(juz_wymuszeni)} ma ją już wymuszoną)."
            )
            return

        PasswordChangeRequired.objects.bulk_create(
            [PasswordChangeRequired(user=u) for u in nowi], ignore_conflicts=True
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Wymuszono zmianę hasła dla {len(nowi)} użytkowników "
                f"({len(juz_wymuszeni)} miało ją już wymuszoną)."
            )
        )
