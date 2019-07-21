from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from bpp.models.cache import Cache_Punktacja_Dyscypliny, Cache_Punktacja_Autora
from bpp.models.sloty.wydawnictwo_ciagle import SlotKalkulator_Wydawnictwo_Ciagle_Prog3
from bpp.models.sloty.wydawnictwo_zwarte import SlotKalkulator_Wydawnictwo_Zwarte_Tier0
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from .exceptions import CannotAdapt
from .wydawnictwo_ciagle import SlotKalkulator_Wydawnictwo_Ciagle_Prog1, SlotKalkulator_Wydawnictwo_Ciagle_Prog2


def ISlot(original):
    if isinstance(original, Wydawnictwo_Ciagle):
        if original.rok in [2017, 2018]:
            if original.punkty_kbn >= 30:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog1(original)
            elif original.punkty_kbn in [20, 25]:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog2(original)
            elif original.punkty_kbn < 20:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog3(original)

        elif original.rok in [2019, 2020]:
            if original.punkty_kbn in [200, 140, 100]:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog1(original)
            elif original.punkty_kbn in [70, 40]:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog2(original)
            elif original.punkty_kbn <= 20:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog3(original)

    elif isinstance(original, Wydawnictwo_Zwarte):
        pass
        # if original.rok in [2017, 2018]:
        #     if original.punkty_kbn in [200, 100, 50]:
        #         raise NotImplementedError("Monografia - tier 2")
        #     elif original.punkty_kbn in [80, ]:  # 20]:
        #         raise NotImplementedError("Monografia - tier 1")
        #     elif original.punkty_kbn in [20, 5]:
        #         return SlotKalkulator_Wydawnictwo_Zwarte_Tier0(original)

    raise CannotAdapt(
        "Nie umiem policzyc dla %s rok %s punkty_kbn %s" % (
            original,
            original.rok,
            original.punkty_kbn))


class IPunktacjaCacher:
    def __init__(self, original):
        self.original = original
        self.slot = None

    def canAdapt(self):
        try:
            self.slot = ISlot(self.original)
            return True

        except CannotAdapt:
            return False

    @transaction.atomic
    def rebuildEntries(self):

        pk = (
            ContentType.objects.get_for_model(self.original).pk,
            self.original.pk
        )

        Cache_Punktacja_Dyscypliny.objects.filter(rekord_id=pk).delete()
        Cache_Punktacja_Autora.objects.filter(rekord_id=pk).delete()

        # Jeżeli nie można zaadaptować danego rekordu do kalkulatora
        # punktacji, to po skasowaniu ewentualnej scache'owanej punktacji
        # wyjdź z funkcji:
        if self.canAdapt() is False:
            return

        _slot_cache = {}

        for dyscyplina in self.slot.dyscypliny:
            _slot_cache[dyscyplina] = self.slot.slot_dla_dyscypliny(dyscyplina)
            Cache_Punktacja_Dyscypliny.objects.create(
                rekord_id=pk,
                dyscyplina=dyscyplina,
                pkd=self.slot.punkty_pkd(dyscyplina),
                slot=_slot_cache[dyscyplina]
            )

        for wa in self.original.autorzy_set.all():
            dyscyplina = wa.okresl_dyscypline()
            if dyscyplina is None:
                continue

            pkdaut = self.slot.pkd_dla_autora(wa)
            if pkdaut is None:
                continue

            Cache_Punktacja_Autora.objects.create(
                rekord_id=pk,
                autor_id=wa.autor_id,
                dyscyplina_id=dyscyplina.pk,
                pkdaut=pkdaut,
                slot=self.slot.slot_dla_autora_z_dyscypliny(dyscyplina)
            )
