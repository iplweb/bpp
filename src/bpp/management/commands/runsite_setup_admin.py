"""Internal management command — wywoływana przez ``run_site``.

Tworzy LUB nadpisuje superusera ``admin/admin`` i czyści wymóg zmiany hasła
z password_policies (jeśli zainstalowane). NIE należy uruchamiać tego ręcznie
poza dev workflow.
"""

from __future__ import annotations

import logging
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Wewnętrzna komenda używana przez run_site — tworzy/nadpisuje "
        "superusera admin/admin i kasuje wymóg zmiany hasła."
    )

    requires_migrations_checks = False

    def handle(self, *args, **opts):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "admin")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@example.com")

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username, defaults={"email": email}
        )
        user.email = email
        user.set_password(password)
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"Superuser {username!r} utworzony."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Superuser {username!r} istnieje — hasło i flagi nadpisane."
                )
            )

        self._clear_password_change_required(user)
        self._refresh_password_history(user)

    def _clear_password_change_required(self, user):
        """Usuń wymóg zmiany hasła z django-password-policies, jeśli istnieje."""
        try:
            from password_policies.models import PasswordChangeRequired
        except ImportError:
            return  # password_policies nie jest zainstalowane — nic do robienia

        deleted, _ = PasswordChangeRequired.objects.filter(user=user).delete()
        if deleted:
            self.stdout.write(
                f"Usunięto {deleted} wpisów PasswordChangeRequired dla {user}."
            )

    def _refresh_password_history(self, user):
        """Dodaj świeży wpis PasswordHistory żeby middleware nie wymuszał zmiany.

        ``password_policies.middleware.PasswordChangeMiddleware`` sprawdza wiek
        ostatniego ``PasswordHistory`` (lub ``date_joined`` jako fallback)
        względem ``PASSWORD_DURATION_SECONDS``. Po restore dump-a wpisy
        admina są stare → hasło uznawane za przeterminowane.

        Dodajemy świeży wpis z ``auto_now_add=True`` (=teraz), więc
        ``get_newest(user)`` zwraca aktualny timestamp i ekspiracja nie
        triggeruje. Stare wpisy zostają — szkody nie robią.
        """
        try:
            from password_policies.models import PasswordHistory
        except ImportError:
            return

        PasswordHistory.objects.create(user=user, password=user.password)
        self.stdout.write(
            f"Dodano świeży wpis PasswordHistory dla {user} "
            "(zapobiega wymuszeniu zmiany hasła)."
        )
