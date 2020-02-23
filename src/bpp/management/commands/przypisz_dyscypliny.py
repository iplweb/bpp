# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import (
    Autor_Dyscyplina,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)
from bpp.models import cache
import logging

logger = logging.getLogger("django")


class Command(BaseCommand):
    help = "Przypisuje dyscypliny do rekordów autorom, na podstawie wpisów Autor_Dyscyplina"

    def add_arguments(self, parser):
        parser.add_argument(
            "--ustawiaj-pierwsza-gdy-dwie",
            action="store_true",
            help="""Dla osób posiadających dwie dysycpliny, ustawiaj zawsze pierwszą dyscyplinę.
            Jeżeli ta opcja nie zostanie określona, osoby posiadające dwie dysycpliny nie będą
            miały ustawianej dyscypliny w swoich rekordach. """,
        )
        parser.add_argument("rok", type=int)
        parser.add_argument("--disable-cache", action="store_true")

    @transaction.atomic
    def handle(self, verbosity, *args, **options):
        if verbosity > 1:
            logger.setLevel(logging.DEBUG)

        logger.debug("ID autora\tAutor\tRok\tDyscyplina\tTytul pracy\tID pracy")
        query = Autor_Dyscyplina.objects.all().exclude(dyscyplina_naukowa=None)

        if not options["ustawiaj_pierwsza_gdy_dwie"]:
            query = query.filter(subdyscyplina_naukowa=None)

        if options["disable_cache"]:
            cache.disable()

        for ad in query:
            for klass in Wydawnictwo_Zwarte_Autor, Wydawnictwo_Ciagle_Autor:
                for instance in klass.objects.filter(
                    autor=ad.autor, rekord__rok=ad.rok, dyscyplina_naukowa=None
                ):
                    logger.debug(
                        f"{ad.autor.pk}\t{ad.autor}\t{ad.rok}\t"
                        f"{ad.dyscyplina_naukowa}\t{instance.rekord.tytul_oryginalny}"
                        f"\t{instance.rekord.pk}"
                    )
                    instance.dyscyplina_naukowa = ad.dyscyplina_naukowa
                    instance.save()
