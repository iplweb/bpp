from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import m2m_changed, post_delete, post_migrate, post_save


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


def _polacz_inwalidacje_menu():
    from nowe_raporty.menu import wyczysc_cache_menu
    from nowe_raporty.models import DefinicjaRaportu

    post_save.connect(wyczysc_cache_menu, sender=DefinicjaRaportu)
    post_delete.connect(wyczysc_cache_menu, sender=DefinicjaRaportu)
    m2m_changed.connect(
        wyczysc_cache_menu, sender=DefinicjaRaportu.wymagane_grupy.through
    )
    m2m_changed.connect(wyczysc_cache_menu, sender=DefinicjaRaportu.uczelnie.through)


class NoweRaportyConfig(AppConfig):
    name = "nowe_raporty"

    def ready(self):
        # Inwalidacja cache menu - zawsze (także w testach).
        _polacz_inwalidacje_menu()

        if settings.TESTING:
            return
        post_migrate.connect(create_entries, sender=self)
        post_migrate.connect(seed_reports, sender=self)
