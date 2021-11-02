from django.db import transaction

from pbn_api.management.commands.util import PBNBaseCommand

from bpp.models import Dyscyplina_Naukowa, Zrodlo


class Command(PBNBaseCommand):
    """Nadpisuje wszystkie dyscypliny dla zrodel z odpowiednikami z PBNu"""

    @transaction.atomic
    def handle(self, verbosity=1, *args, **options):

        dyscypliny = {x.kod: x for x in Dyscyplina_Naukowa.objects.all()}
        missing = set()
        for zrodlo in Zrodlo.objects.exclude(pbn_uid_id=None):
            zrodlo.dyscyplina_zrodla_set.all().delete()

            areas = zrodlo.pbn_uid.value("object", "areas", return_none=True)
            if not areas:
                continue

            for code in areas:
                kod_dyscypliny = "%i.%i" % (int(code[0]), int(code[1:]))
                if kod_dyscypliny not in dyscypliny:
                    if kod_dyscypliny not in missing:
                        print(f"BRAK KODU DYSCYPLINY: {kod_dyscypliny}")
                        missing.add(kod_dyscypliny)
                    continue

                zrodlo.dyscyplina_zrodla_set.create(
                    dyscyplina=dyscypliny[kod_dyscypliny]
                )
