from decimal import Decimal

from bpp import const
from bpp.models.sloty.wydawnictwo_ciagle import (
    SlotKalkulator_Wydawnictwo_Ciagle_Prog1,
    SlotKalkulator_Wydawnictwo_Ciagle_Prog2,
    SlotKalkulator_Wydawnictwo_Ciagle_Prog3,
)


class SlotKalkulator_Wydawnictwo_Zwarte_Baza:
    """
    W przypadku prac HST+nie-HST wymagamy _zwykłej_ punktacji PK czyli nie-powiększonej
    (80, 200 itp).
    """

    def __init__(self, original, tryb_kalkulacji, wiele_hst=False, poziom_wydawcy=None):
        self.original = original
        self.tryb_kalkulacji = tryb_kalkulacji
        self.wiele_hst = wiele_hst
        self.poziom_wydawcy = poziom_wydawcy

    def punkty_pkd(self, dyscyplina):
        val = super().punkty_pkd(dyscyplina)
        if not self.wiele_hst:
            return val

        # Jeżeli jest włączony tryb HST to pomnóz 1.5 razy:
        if val is not None and dyscyplina.dyscyplina_hst:
            # UWAGA ** UWAGA ** UWAGA
            #
            # Ta procedura da dobry wynik tak długo, jak długo punkty PK będą w "liczniku" czyli
            # całe działanie (zwracane przez super().punkty_pkd(dyscyplina) będzie możliwe do przemnożenia
            # przez 1.5.  Do tego, podnosi tą wartość wyłącznie dla dyscyplin HST. Z wyłaczeniem rozdziału
            # i redakcji monografii na poziomie 1, gdyż tam mnożnik wynosi 1.0
            #

            mnoznik = Decimal("1.5")

            if (
                self.tryb_kalkulacji
                in [
                    const.TRYB_KALKULACJI.ROZDZIAL_W_MONOGRAFI,
                    const.TRYB_KALKULACJI.REDAKCJA_MONOGRAFI,
                ]
                and self.poziom_wydawcy == 1
            ):
                mnoznik = Decimal("1.0")

            return val * mnoznik

        return val


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
