# -*- encoding: utf-8 -*-
import logging

from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Q

from bpp.models import Wydawnictwo_Zwarte, Wydawca
from bpp.models.struktura import Jednostka, Uczelnia


class Command(BaseCommand):
    help = "Dzieli podwojnych (oddzielonych srednikiem) wydawcow"

    @transaction.atomic
    def handle(self, *args, **options):
        verbosity = int(options["verbosity"])
        logger = logging.getLogger("django")
        if verbosity > 1:
            logger.setLevel(logging.DEBUG)

        for rec in Wydawnictwo_Zwarte.objects.exclude(wydawca=None).filter(
            wydawca__nazwa__contains=";"
        ):
            nazwa_wydawcy = rec.wydawca.nazwa

            z_poziomami = []
            bez_poziomow = []

            logger.info("")
            logger.info(f"Rekord: {rec}")
            logger.info(f". ma takiego wydawcę: {nazwa_wydawcy}")

            for elem in rec.wydawca.nazwa.split(";"):
                elem = elem.strip()
                try:
                    nw = Wydawca.objects.get(nazwa=elem)
                    ma_poziomy = nw.poziom_wydawcy_set.exists()
                    logger.info(f"+ człon {elem} -> {nw}, ma_poziomy: {ma_poziomy}...")
                except Wydawca.DoesNotExist:
                    logger.info(f"- człon {elem} nie pasuje nigdzie...")
                    continue

                if ma_poziomy:
                    z_poziomami.append(nw)
                else:
                    bez_poziomow.append(nw)

            for tablica in [z_poziomami, bez_poziomow]:
                if not tablica:
                    continue

                for wydawca in tablica:
                    rec.wydawca = wydawca
                    rec.wydawca_opis = nazwa_wydawcy.replace(rec.wydawca.nazwa, "")
                    rec.save()
                    logger.info(
                        f"-> zmienie go na {wydawca.nazwa}, reszta {rec.wydawca_opis}"
                    )
                    break
                break
