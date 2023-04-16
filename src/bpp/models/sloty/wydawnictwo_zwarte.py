from bpp.models.sloty.wydawnictwo_ciagle import (
    SlotKalkulator_Wydawnictwo_Ciagle_Prog1,
    SlotKalkulator_Wydawnictwo_Ciagle_Prog2,
    SlotKalkulator_Wydawnictwo_Ciagle_Prog3,
)


class SlotKalkulator_Wydawnictwo_Zwarte_Baza:
    def __init__(self, original, tryb_kalkulacji):
        self.original = original
        self.tryb_kalkulacji = tryb_kalkulacji


class SlotKalkulator_Wydawnictwo_Zwarte_Prog3(
    SlotKalkulator_Wydawnictwo_Zwarte_Baza, SlotKalkulator_Wydawnictwo_Ciagle_Prog3
):
    """
    Wydawnictwo zwarte - próg trzeci, ostatni
    Monografia - wydawnictwo spoza wykazu wydawców

    PK 20 + książka autorstwo (HST 20 lub HST 120 gdy KEN+),
    PK 5 + książka redakcja (HST 10 lub HST 20 gdy KEN+),
    PK 5 + rozdział (HST 5 lub HST 20 gdy KEN+)
    """


class SlotKalkulator_Wydawnictwo_Zwarte_Prog2(
    SlotKalkulator_Wydawnictwo_Zwarte_Baza, SlotKalkulator_Wydawnictwo_Ciagle_Prog2
):
    """
    Wydawnictwo zwarte - próg drugi,
    Monografia - wydawnictwo poziom 1,

    PK 80 + ksiązka autorstwo (HST 120)
    PK 20 + książka redakcja (HST 40),
    Pk 20 + rozdział (HST 20),
    """


class SlotKalkulator_Wydawnictwo_Zwarte_Prog1(
    SlotKalkulator_Wydawnictwo_Zwarte_Baza, SlotKalkulator_Wydawnictwo_Ciagle_Prog1
):
    """
    Wydawnictwo zwarte - próg pierwszy
    Monogafia - wydawnictwo poziom 2,

    PK 200 + książka autorstwo (HST 300)
    PK 100 + ksiażka redkacja (HST 150),
    PK 50 + rozdział (HST 75),
    """
