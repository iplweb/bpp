from django.apps import AppConfig


class ZglosPublikacjeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "zglos_publikacje"
    verbose_name = "Zgłoszenia publikacji"

    def ready(self):
        # Rejestruje system-check ALTCHA (captcha ON + klucz-placeholder).
        # Rejestracja zgłoszeń w reversion (historia zmian w adminie).
        from . import (
            checks,  # noqa: F401
            wersjonowanie,  # noqa: F401
        )
