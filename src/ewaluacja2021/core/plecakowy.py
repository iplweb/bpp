from django.db.models import Sum

from .ewaluacja3n_base import Ewaluacja3NBase
from .util import policz_knapsack

from bpp.models import Cache_Punktacja_Autora_Query
from bpp.util import pbar


class Plecakowy(Ewaluacja3NBase):
    def __init__(
        self,
        nazwa_dyscypliny="nauki medyczne",
        bez_limitu_uczelni=False,
        output_path=None,
    ):
        Ewaluacja3NBase.__init__(
            self=self, nazwa_dyscypliny=nazwa_dyscypliny, output_path=output_path
        )
        self.bez_limitu_uczelni = bez_limitu_uczelni
        self.get_data()

    @property
    def lista_prac(self):
        return self.lista_prac_tuples

    def get_lista_autorow_w_kolejnosci(self):

        punkty_na_id_autora = {
            i["autor_id"]: i["pkdaut__sum"]
            for i in Cache_Punktacja_Autora_Query.objects.values("autor_id").annotate(
                Sum("pkdaut")
            )
        }

        id_autorow = sorted(
            list(self.id_wszystkich_autorow),
            key=lambda item: punkty_na_id_autora[item],
            reverse=True,
        )

        return id_autorow

    def sumuj(self):

        for autor_id in pbar(self.get_lista_autorow_w_kolejnosci()):

            if self.bez_limitu_uczelni:
                wszystkie = list(
                    praca for praca in self.lista_prac_db.filter(autor_id=autor_id)
                )
            else:
                wszystkie = list(
                    praca
                    for praca in self.lista_prac_db.filter(autor_id=autor_id)
                    if self.czy_moze_przejsc_warunek_uczelnia(praca)
                )

            monografie = [x for x in wszystkie if x.monografia]
            nie_monografie = [x for x in wszystkie if not x.monografia]

            maksymalny_slot_za_calosc = self.maks_pkt_aut_calosc.get(autor_id)
            maksymalny_slot_za_monografie = self.maks_pkt_aut_monografie.get(autor_id)

            pkt_monografie, prace_monografie = policz_knapsack(
                monografie,
                maks_slot=maksymalny_slot_za_monografie,
            )
            potencjalny_slot_za_zdane_monografie = sum(x.slot for x in prace_monografie)

            pkt_nie_monografie_maks, prace_nie_monografie_maks = policz_knapsack(
                nie_monografie,
                maks_slot=maksymalny_slot_za_calosc,
            )

            pkt_nie_monografie_min, prace_nie_monografie_min = policz_knapsack(
                nie_monografie,
                maks_slot=maksymalny_slot_za_calosc
                - potencjalny_slot_za_zdane_monografie,
            )

            if pkt_nie_monografie_maks > (pkt_nie_monografie_min + pkt_monografie):
                [self.zsumuj_pojedyncza_prace(x) for x in prace_nie_monografie_maks]
            else:
                [self.zsumuj_pojedyncza_prace(x) for x in prace_monografie]
                [self.zsumuj_pojedyncza_prace(x) for x in prace_nie_monografie_min]
