from django.apps import AppConfig
from django.conf import settings


class NoweRaportyConfig(AppConfig):
    name = "nowe_raporty"

    def ready(self):
        if getattr(settings, "TESTING"):
            return

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
