from django.apps import AppConfig


class PbnImportConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "pbn_import"
    verbose_name = "PBN Import"

    def ready(self):
        # Import signal handlers when app is ready
        try:
            pass
        except ImportError:
            pass
