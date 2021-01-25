from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_migrate


def create_entries(sender, **kw):
    from .views.autor import WyborOsoby
    from .views.ewaluacja import ParametryRaportSlotowEwaluacja
    from .views.uczelnia import UtworzRaportSlotowUczelnia

    for elem in (
        WyborOsoby,
        ParametryRaportSlotowEwaluacja,
        UtworzRaportSlotowUczelnia,
    ):
        elem().get_initial()


class RaportSlotowConfig(AppConfig):
    name = "raport_slotow"

    def ready(self):
        if getattr(settings, "TESTING"):
            return
        post_migrate.connect(create_entries, sender=self)
