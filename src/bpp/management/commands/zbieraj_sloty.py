import logging
import sys
from decimal import Decimal

from django.core.management import BaseCommand
from django.core.management.base import CommandError
from django.db import transaction

from bpp.models import Autor, Cache_Punktacja_Autora, Rekord, Uczelnia

logger = logging.getLogger("django")


class Command(BaseCommand):
    help = "Zbiera sloty dla danego autora"

    def add_arguments(self, parser):
        parser.add_argument("autor_id", type=int, help="ID autora")
        parser.add_argument("--slot", type=int, default=4, help="Ile slotow zbierac")
        parser.add_argument("--xls", default=None)

        parser.add_argument(
            "--rok_min",
            type=int,
            default=2017,
        )
        parser.add_argument(
            "--rok_max",
            type=int,
            default=2020,
        )
        parser.add_argument(
            "--uczelnia",
            type=int,
            default=None,
            help="ID uczelni (wymagane gdy >1 uczelnia)",
        )

    def _resolve_uczelnia(self, uczelnia_id):
        """Uczelnia dla komendy CLI (single-or-fail).

        - ``--uczelnia`` zawsze honorowane (i walidowane),
        - przy dokładnie jednej uczelni używamy jej (``get()`` — count==1),
        - przy wielu uczelniach brak ``--uczelnia`` to ``CommandError`` —
          bez cichego wyboru pierwszej-z-brzegu.
        """
        if uczelnia_id is not None:
            try:
                return Uczelnia.objects.get(pk=uczelnia_id)
            except Uczelnia.DoesNotExist as e:
                raise CommandError(f"Brak uczelni o id={uczelnia_id}.") from e

        count = Uczelnia.objects.count()
        if count == 0:
            return None
        if count == 1:
            return Uczelnia.objects.get()
        raise CommandError(
            "W systemie jest więcej niż jedna uczelnia — podaj --uczelnia, "
            "żeby ograniczyć zbieranie slotów do jednej uczelni."
        )

    @transaction.atomic
    def handle(
        self,
        autor_id,
        slot,
        rok_min,
        rok_max,
        verbosity,
        xls,
        uczelnia,
        *args,
        **options,
    ):
        autor = Autor.objects.get(id=autor_id)
        uczelnia_obj = self._resolve_uczelnia(uczelnia)

        res, lista = autor.zbieraj_sloty(
            slot,
            rok_min,
            rok_max,
            uczelnia_id=uczelnia_obj.pk if uczelnia_obj else None,
        )

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
