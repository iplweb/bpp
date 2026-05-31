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


def seed_reports(sender, **kw):
    # Zaloz domyslne definicje raportow na swiezym deployu. Idempotentne i
    # nienadpisujace - patrz nowe_raporty.seeding.
    from nowe_raporty.seeding import seed_default_reports

    seed_default_reports()


class NoweRaportyConfig(AppConfig):
    name = "nowe_raporty"

    def ready(self):
        if settings.TESTING:
            return
        post_migrate.connect(create_entries, sender=self)
        post_migrate.connect(seed_reports, sender=self)
