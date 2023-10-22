import argparse
import logging

from django.db import transaction
from django.db.transaction import TransactionManagementError

from pbn_api.management.commands.util import PBNBaseCommand

from bpp.models import Dyscyplina_Naukowa, Punktacja_Zrodla, Zrodlo

logger = logging.getLogger("console.always")


class DryRunException(TransactionManagementError):
    pass


class Command(PBNBaseCommand):
    """Nadpisuje wszystkie dyscypliny dla zrodel z odpowiednikami z PBNu"""

    def add_arguments(self, parser):
        parser.add_argument("--min-rok", type=int, default=2022)
        parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction)

    @transaction.atomic
    def handle(self, min_rok, dry_run, verbosity=1, *args, **options):
        dyscypliny = {x.kod: x for x in Dyscyplina_Naukowa.objects.all()}
        missing = set()
        for zrodlo in Zrodlo.objects.exclude(pbn_uid_id=None).select_related("pbn_uid"):
            # import punktow
            points = zrodlo.pbn_uid.value("object", "points", return_none=True)
            if points is None:
                points = []
            for rok in points:
                if int(rok) < min_rok:
                    continue

                punkty = points[rok]["points"]
                try:
                    pzr = zrodlo.punktacja_zrodla_set.get(rok=rok)
                except Punktacja_Zrodla.DoesNotExist:
                    logger.info(
                        f"IDZ-4: tworze nowy wpis punktacji zrodla; za rok; {rok}; "
                        f"{zrodlo.nazwa}; punkty; {punkty}"
                    )
                    zrodlo.punktacja_zrodla_set.create(punkty_kbn=punkty, rok=rok)
                    continue

                if pzr.punkty_kbn != punkty:
                    logger.info(
                        f"IDZ-5: zrodlo; {zrodlo.nazwa}; rok; {rok}; BPP ma punktow; "
                        f"{pzr.punkty_kbn}; a w PBN jest; {punkty}; ustawiam na PBN"
                    )

                    pzr.punkty_kbn = punkty
                    pzr.save()
            else:
                logger.info(
                    f"IDZ-6; zrodlo; {zrodlo.nazwa}; nie zawiera danych o punktach po stronie PBN"
                )

            # Import dyscyplin

            # Aktualne dyscypliny:
            aktualne_dyscypliny_zrodla = set(
                zrodlo.dyscyplina_zrodla_set.all().values_list(
                    "dyscyplina__nazwa", flat=True
                )
            )

            # Ustawmy mu wszystkie dyscypliny wg zawartości PBN API:
            zrodlo.dyscyplina_zrodla_set.all().delete()

            areas = zrodlo.pbn_uid.value("object", "areas", return_none=True)
            if not areas:
                logger.info(
                    f"IDZ-1: źródło {zrodlo.pbn_uid} nie zawiera informacji o dyscyplinach"
                )
                continue

            for code in areas:
                kod_dyscypliny = "%i.%i" % (int(code[0]), int(code[1:]))
                if kod_dyscypliny not in dyscypliny:
                    if kod_dyscypliny not in missing:
                        logger.info(
                            f"IDZ-0: po stronie BPP brak kodu dyscypliny: {kod_dyscypliny}"
                        )
                        missing.add(kod_dyscypliny)
                    continue

                # Tu zamiast .create użyjemy .get_or_create, bo po stronie PBNu
                # najwyraźniej lista może zawierac ten sam element kilka razy:
                zrodlo.dyscyplina_zrodla_set.get_or_create(
                    dyscyplina_id=dyscypliny[kod_dyscypliny].pk
                )

            # Nowe dyscypliny:
            nowe_dyscypliny_zrodla = set(
                zrodlo.dyscyplina_zrodla_set.all().values_list(
                    "dyscyplina__nazwa", flat=True
                )
            )

            # Roznica:
            dodane = nowe_dyscypliny_zrodla.difference(aktualne_dyscypliny_zrodla)
            usuniete = aktualne_dyscypliny_zrodla.difference(nowe_dyscypliny_zrodla)

            if dodane:
                logger.info(f"IDZ-2: {zrodlo.nazwa} ;+++   DODANE; {dodane}")

            if usuniete:
                logger.info(f"IDZ-3: {zrodlo.nazwa} ;--- USUNIETE; {usuniete}")

        if dry_run:
            raise DryRunException(
                "IDZ-X: podano opcję --dry-run, wywołuję błąd, aby wycofać zmiany"
            )
