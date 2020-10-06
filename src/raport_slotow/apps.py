from django.apps import AppConfig
from django.conf import settings


class RaportSlotowConfig(AppConfig):
    name = "raport_slotow"

    def ready(self):
        if getattr(settings, "TESTING"):
            return

        from .views.autor import WyborOsoby
        from .views.uczelnia import ParametryRaportSlotowUczelnia
        from .views.ewaluacja import ParametryRaportSlotowEwaluacja

        for elem in (
            WyborOsoby,
            ParametryRaportSlotowEwaluacja,
            ParametryRaportSlotowUczelnia,
        ):
            elem().get_initial()
