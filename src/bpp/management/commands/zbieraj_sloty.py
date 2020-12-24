# -*- encoding: utf-8 -*-
import sys
from decimal import Decimal

from django.core.management import BaseCommand
from django.db import transaction

import logging

from bpp.models import Autor, Rekord, Cache_Punktacja_Autora

logger = logging.getLogger("django")


class Command(BaseCommand):
    help = "Zbiera sloty dla danego autora"

    def add_arguments(self, parser):
        parser.add_argument("autor_id", type=int, help="ID autora")
        parser.add_argument("--slot", type=int, default=4, help="Ile slotow zbierac")
        parser.add_argument("--xls", default=None)

        parser.add_argument(
            "--rok_min", type=int, default=2017,
        )
        parser.add_argument(
            "--rok_max", type=int, default=2020,
        )

    @transaction.atomic
    def handle(
        self, autor_id, slot, rok_min, rok_max, verbosity, xls, *args, **options
    ):
        autor = Autor.objects.get(id=autor_id)

        res, lista = autor.zbieraj_sloty(slot, rok_min, rok_max)

        wiersze = []
        wiersze.append(["Parametry:"])
        wiersze.append(["Autor", str(autor)])
        wiersze.append(["Rok min", str(rok_min)])
        wiersze.append(["Rok max", str(rok_max)])
        wiersze.append(["Zbierac do: ", str(slot)])
        wiersze.append([])
        wiersze.append(["Zebrano punktow", str(res)])
        wiersze.append([])

        prace = []
        prace.append(["Prace:"])
        prace.append(["Rok", "ID", "Slot", "PKdAut", "Tytuł (skrócony)"])
        suma_slotow = Decimal("0.0000")
        for elem in lista:
            r = Rekord.objects.get(pk=elem)
            cpa = Cache_Punktacja_Autora.objects.get(rekord_id=r.pk, autor=autor)
            suma_slotow += cpa.slot
            prace.append(
                [
                    str(r.rok),
                    str(r.pk),
                    str(cpa.slot).replace(".", ","),
                    str(cpa.pkdaut).replace(".", ","),
                    str(r.tytul_oryginalny[:80]),
                ]
            )

        wiersze.append(["Zebrano slot(ow):", str(suma_slotow)])
        wiersze.append([])

        if not xls:
            for w in wiersze + prace:
                print("\t".join(w))
            sys.exit(0)

        import openpyxl

        wb = openpyxl.Workbook()
        s = wb.worksheets[0]
        for w in wiersze + prace:
            s.append(w)
        wb.save(xls)
