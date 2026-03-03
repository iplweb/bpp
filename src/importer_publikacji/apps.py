from django.apps import AppConfig


class ImporterPublikacjiConfig(AppConfig):
    name = "importer_publikacji"
    verbose_name = "Importer publikacji"
    default_auto_field = "django.db.models.AutoField"

    def ready(self):
        from .providers import bibtex, crossref, dspace, pbn, www  # noqa: F401
