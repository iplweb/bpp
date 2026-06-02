"""
Modele abstrakcyjne związane z przeliczaniem dyscyplin.
"""

from django.db import models


class ModelZPrzeliczaniemDyscyplin(models.Model):
    class Meta:
        abstract = True

    def przelicz_punkty_dyscyplin(self, uczelnia=None):
        from bpp.models.sloty.core import IPunktacjaCacher

        if uczelnia is None:
            from bpp.models.uczelnia import Uczelnia

            # TODO(multi-hosted): patrz ISlot — punktacja docelowo per-uczelnia,
            # osobny redesign warstwy ewaluacji. Do tego czasu get_default()
            # (NIE .get() — hot-path per-save).
            uczelnia = Uczelnia.objects.get_default()

        ipc = IPunktacjaCacher(self, uczelnia)
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
