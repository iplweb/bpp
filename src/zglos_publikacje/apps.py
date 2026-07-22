from django.apps import AppConfig


class ZglosPublikacjeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "zglos_publikacje"

    def ready(self):
        # Rejestruje system-check ALTCHA (captcha ON + klucz-placeholder).
        from . import checks  # noqa: F401
