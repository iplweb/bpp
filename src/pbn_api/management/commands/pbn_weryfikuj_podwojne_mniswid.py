import logging

from django.db import transaction

from pbn_api.management.commands.util import PBNBaseCommand
from pbn_api.models import Journal

from bpp.models import Zrodlo

logger = logging.getLogger("console.always")


def weryfikuj(zrodlo: Zrodlo, inny_journal: Journal):
    for elem, label in [("areas", "dyscyplinach"), ("points", "punktach")]:
        data_zrodlo = zrodlo.pbn_uid.value("object", elem, return_none=True)
        data_nowy = inny_journal.value("object", elem, return_none=True)
        if data_zrodlo is None and data_nowy is not None:
            logger.info(
                f"WPM-0: Zrodlo {zrodlo} ma odpowiednik w PBN {zrodlo.pbn_uid} i nie ma tam informacji o {label}, "
                f"ale wystarczy zamienić go na {inny_journal}, bo w tym innym wpisie są.\n"
            )
            return True


class Command(PBNBaseCommand):
    """Weryfikuje przypisania do PBNu pod kątem występowania ich alternatyw z określonym
    MNISWID + opisem dyscyplin"""

    def add_arguments(self, parser):
        parser.add_argument("--przemapuj", type=bool, default=False)

    @transaction.atomic
    def handle(self, przemapuj, verbosity=1, *args, **options):
        if not przemapuj:
            logger.info(
                "Uruchom z argumentem --przemapuj=true aby faktycznie przemapować odpowiedniki"
            )
        for zrodlo in Zrodlo.objects.exclude(pbn_uid_id=None).select_related("pbn_uid"):
            # Znajdź źródło o takim samym ISSN co przypisane ale z innym MNISWID

            alternatywy = set()

            if zrodlo.pbn_uid.issn:
                alternatywy.update(
                    {
                        x
                        for x in Journal.objects.exclude(mongoId=zrodlo.pbn_uid_id)
                        .filter(issn=zrodlo.pbn_uid.issn)
                        .exclude(mniswId=None)
                    }
                )

                alternatywy.update(
                    {
                        x
                        for x in Journal.objects.exclude(mongoId=zrodlo.pbn_uid_id)
                        .filter(eissn=zrodlo.pbn_uid.issn)
                        .exclude(mniswId=None)
                    }
                )

            if zrodlo.pbn_uid.eissn:
                alternatywy.update(
                    {
                        x
                        for x in Journal.objects.exclude(mongoId=zrodlo.pbn_uid_id)
                        .filter(issn=zrodlo.pbn_uid.eissn)
                        .exclude(mniswId=None)
                    }
                )

                alternatywy.update(
                    {
                        x
                        for x in Journal.objects.exclude(mongoId=zrodlo.pbn_uid_id)
                        .filter(eissn=zrodlo.pbn_uid.eissn)
                        .exclude(mniswId=None)
                    }
                )

            if alternatywy:
                for alternatywa in alternatywy:
                    if weryfikuj(zrodlo, alternatywa) and przemapuj:
                        zrodlo.pbn_uid = alternatywa
                        zrodlo.save(update_fields=["pbn_uid"])
                        logger.info(
                            f"WPM-1: ustawiam {alternatywa} jako odpowiednik dla {zrodlo}"
                        )
                        break
