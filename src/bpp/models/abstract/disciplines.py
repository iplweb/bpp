"""
Modele abstrakcyjne związane z przeliczaniem dyscyplin.
"""

from django.db import models


class ModelZPrzeliczaniemDyscyplin(models.Model):
    class Meta:
        abstract = True

    def przelicz_punkty_dyscyplin(self):
        from bpp.models.sloty.core import IPunktacjaCacher

        ipc = IPunktacjaCacher(self)
        ipc.removeEntries()
        if ipc.canAdapt():
            ipc.rebuildEntries()
        return ipc.serialize()

    def odpiete_dyscypliny(self):
        return self.autorzy_set.exclude(dyscyplina_naukowa=None).exclude(przypieta=True)

    def wszystkie_dyscypliny_rekordu(self, uczelnia=None):
        """Każda dyscyplina przypięta do pracy.

        Gdy podano `uczelnia`, zawęża do autorów tej uczelni
        (autor → jednostka → uczelnia) — pod per-uczelniane rozstrzyganie
        wiele_hst. Bez uczelni: globalnie (jak dawniej).
        """
        if not self.pk:
            return []

        qs = self.autorzy_set.exclude(dyscyplina_naukowa=None).filter(przypieta=True)
        if uczelnia is not None:
            qs = qs.filter(jednostka__uczelnia=uczelnia)
        return qs.values_list("dyscyplina_naukowa").distinct()

    def uczelnie_rekordu(self):
        """Distinct uczelnie wśród afiliujących, przypiętych autorów rekordu
        (autor → jednostka → uczelnia). Luźny nadzbiór wystarcza."""
        from bpp.models.uczelnia import Uczelnia

        if not self.pk:
            return Uczelnia.objects.none()

        uczelnia_ids = (
            self.autorzy_set.filter(afiliuje=True, przypieta=True)
            .values_list("jednostka__uczelnia_id", flat=True)
            .distinct()
        )
        return Uczelnia.objects.filter(pk__in=list(uczelnia_ids))
