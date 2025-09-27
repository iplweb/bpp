from django.apps import AppConfig


class PbnExportQueueConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "pbn_export_queue"
    verbose_name = "Kolejka eksportu do PBN"
