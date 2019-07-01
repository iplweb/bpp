from bpp.models import Wydawnictwo_Zwarte, Wydawnictwo_Ciagle

from .wydawnictwo_ciagle import SlotKalkulator_Wydawnictwo_Ciagle_Prog1, SlotKalkulator_Wydawnictwo_Ciagle_Prog2

def ISlot(original):
    if isinstance(original, Wydawnictwo_Ciagle):
        if original.rok in [2017, 2018]:
            if original.punkty_kbn >= 30:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog1(original)
            elif original.punkty_kbn in [20, 25]:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog2(original)
            elif original.punkty_bkn < 20:
                raise NotImplementedError
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
