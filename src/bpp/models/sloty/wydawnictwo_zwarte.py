from bpp.models import mnoznik_dla_monografii, const
from bpp.models.sloty.wydawnictwo_ciagle import SlotKalkulator_Wydawnictwo_Ciagle_Prog3, \
    SlotKalkulator_Wydawnictwo_Ciagle_Prog2, SlotKalkulator_Wydawnictwo_Ciagle_Prog1


class SKWZMixin:
    def __init__(self, original, tryb_kalkulacji):
        self.original = original
        self.tryb_kalkulacji = tryb_kalkulacji

    def mnoznik(self, dyscyplina):
        if self.tryb_kalkulacji is not None:
            kod_dziedziny = dyscyplina.kod_dziedziny()
            if kod_dziedziny is not None:
                return mnoznik_dla_monografii(
                    const.DZIEDZINA(kod_dziedziny),
                    self.tryb_kalkulacji,
                    self.original.punkty_kbn)

        return 1


class SlotKalkulator_Wydawnictwo_Zwarte_Prog3(SKWZMixin, SlotKalkulator_Wydawnictwo_Ciagle_Prog3):
    """
    Wydawnictwo zwarte - próg trzeci, ostatni
    Monografia - wydawnictwo spoza wykazu wydawców

    PK 20 + książka autorstwo,
    PK 5 + książka redakcja,
    PK 5 + rozdział.
    """
    pass


class SlotKalkulator_Wydawnictwo_Zwarte_Prog2(SKWZMixin, SlotKalkulator_Wydawnictwo_Ciagle_Prog2):
    """
    Wydawnictwo zwarte - próg drugi,
    Monografia - wydawnictwo poziom 1,

    PK 80 + ksiązka autorstwo,
    PK 20 + książka redakcja,
    Pk 20 + rozdział.
    """
    pass


class SlotKalkulator_Wydawnictwo_Zwarte_Prog1(SKWZMixin, SlotKalkulator_Wydawnictwo_Ciagle_Prog1):
    """
    Wydawnictwo zwarte - próg pierwszy
    Monogafia - wydawnictwo poziom 2,

    PK 200 + książka autorstwo,
    PK 100 + ksiażka redkacja,
    PK 50 + rozdział.
    """
    pass
