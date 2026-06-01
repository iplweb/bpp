from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import m2m_changed, post_delete, post_migrate, post_save


def create_entries(sender, **kw):
    # Zarejestruj formdefaults per DefinicjaRaportu (dynamiczna klasa formularza
    # ma unikalny full_name -> osobny rekord defaultow per raport). Wymaga, by
    # DefinicjaRaportu juz istnialy (seed_reports musi polecic wczesniej).
    from formdefaults.core import get_form_defaults

    from nowe_raporty.forms import form_class_dla
    from nowe_raporty.models import DefinicjaRaportu

    for definicja in DefinicjaRaportu.objects.all():
        form_class = form_class_dla(definicja)
        get_form_defaults(form_class(), definicja.nazwa, user=None)


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
        # Kolejnosc wazna: seed tworzy DefinicjaRaportu, potem create_entries
        # rejestruje dla nich formdefaults.
        post_migrate.connect(seed_reports, sender=self)
        post_migrate.connect(create_entries, sender=self)
