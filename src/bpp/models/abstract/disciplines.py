"""
Modele abstrakcyjne związane z przeliczaniem dyscyplin.
"""

from django.db import models


class ModelZPrzeliczaniemDyscyplin(models.Model):
    class Meta:
        abstract = True

    def przelicz_punkty_dyscyplin(self):
        from bpp.models.sloty.core import IPunktacjaCacher
        from bpp.models.uczelnia import Uczelnia

        ipc = IPunktacjaCacher(self, Uczelnia.objects.get_default())
        ipc.removeEntries()
        if ipc.canAdapt():
            ipc.rebuildEntries()
        return ipc.serialize()

    def odpiete_dyscypliny(self):
        return self.autorzy_set.exclude(dyscyplina_naukowa=None).exclude(przypieta=True)

    def wszystkie_dyscypliny_rekordu(self):
        """Ta funkcja zwraca każdą dyscyplinę przypiętą do pracy w postaci listy."""
        if not self.pk:
            return []

        return (
            self.autorzy_set.exclude(dyscyplina_naukowa=None)
            .filter(przypieta=True)
            .values_list("dyscyplina_naukowa")
            .distinct()
        )
