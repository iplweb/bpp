from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_migrate


def create_entries(sender, **kw):

    from nowe_raporty.views import (
        AutorRaportFormView,
        JednostkaRaportFormView,
        WydzialRaportFormView,
    )

    for elem in [
        AutorRaportFormView,
        JednostkaRaportFormView,
        WydzialRaportFormView,
    ]:
        # Stwórz inicjalną wersję bazodanową formularza przy starcie aplikacji
        elem().get_initial()


class NoweRaportyConfig(AppConfig):
    name = "nowe_raporty"

    def ready(self):
        if getattr(settings, "TESTING"):
            return
        post_migrate.connect(create_entries, sender=self)
