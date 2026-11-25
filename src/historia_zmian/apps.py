from django.apps import AppConfig


class HistoriaZmianConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "historia_zmian"
    verbose_name = "Historia zmian"

    def ready(self):
        from . import receivers  # noqa: F401
        from .archiwum_plikow import podlacz

        podlacz()
