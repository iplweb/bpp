from django.apps import AppConfig


class DjangoCountdownConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_countdown"
    verbose_name = "Odliczanie do zamknięcia serwisu"
