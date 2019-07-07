from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from bpp.models import Wydawnictwo_Zwarte, Wydawnictwo_Ciagle, Cache_Punktacja_Dyscypliny, Cache_Punktacja_Autora, \
    Dyscyplina_Naukowa
from bpp.models.sloty.wydawnictwo_ciagle import SlotKalkulator_Wydawnictwo_Ciagle_Prog3
from bpp.models.sloty.wydawnictwo_zwarte import SlotKalkulator_Wydawnictwo_Zwarte_Tier0

from .wydawnictwo_ciagle import SlotKalkulator_Wydawnictwo_Ciagle_Prog1, SlotKalkulator_Wydawnictwo_Ciagle_Prog2

from .exceptions import CannotAdapt


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

        else:
            raise NotImplementedError

    elif isinstance(original, Wydawnictwo_Zwarte):
        if original.rok in [2017, 2018]:
            if original.punkty_kbn in [200, 100, 50]:
                raise NotImplementedError("Monografia - tier 2")
            elif original.punkty_kbn in [80, ]:  # 20]:
                raise NotImplementedError("Monografia - tier 1")
            elif original.punkty_kbn in [20, 5]:
                return SlotKalkulator_Wydawnictwo_Zwarte_Tier0(original)
            else:
                raise NotImplementedError(
                    "Punkty KBN %i nie obslugiwane dla %s" % (original.punkty_kbn, original._meta.model_name))

        raise NotImplementedError("Rok %i nie obslugiwany dla %s" % (original.rok, original._meta.model_name))

    else:
        raise NotImplementedError("Obsługa typu %s nie zaimplementowana" % original)


class IPunktacjaCacher:
    def __init__(self, original):
        self.original = original
        self.slot = None


    def canAdapt(self):
        try:
            self.slot = ISlot(self.original)
        except (CannotAdapt, NotImplementedError):
            return False
        return True

    @transaction.atomic
    def rebuildEntries(self):
        if self.slot is None:
            assert self.canAdapt() is True

        pk = (
            ContentType.objects.get_for_model(self.original).pk,
            self.original.pk
        )

        Cache_Punktacja_Dyscypliny.objects.filter(rekord_id=pk).delete()
        Cache_Punktacja_Autora.objects.filter(rekord_id=pk).delete()

        _slot_cache = {}
        dyscypliny = dict([(x.pk, x) for x in Dyscyplina_Naukowa.objects.all()])

        for dyscyplina_id in self.slot.dyscypliny:
            dyscyplina = dyscypliny[dyscyplina_id]

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

            Cache_Punktacja_Autora.objects.create(
                rekord_id=pk,
                autor_id=wa.autor_id,
                dyscyplina_id=dyscyplina.pk,
                pkdaut=self.slot.pkd_dla_autora(wa),
                slot=self.slot.slot_dla_autora_z_dyscypliny(dyscyplina)
            )
