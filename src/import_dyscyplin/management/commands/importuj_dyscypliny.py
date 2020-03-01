# -*- encoding: utf-8 -*-

import logging
from argparse import FileType
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import File
from django.core.management.base import BaseCommand

from import_dyscyplin.models import Import_Dyscyplin
from import_dyscyplin.tasks import (
    integruj_import_dyscyplin,
    przeanalizuj_import_dyscyplin,
    stworz_kolumny,
)

logger = logging.getLogger("django")


class Command(BaseCommand):
    help = "Importuje dyscypliny z zadanego pliku"

    def add_arguments(self, parser):
        parser.add_argument("rok", type=int)
        parser.add_argument("path", type=FileType("rb"))

    def handle(self, rok, path, verbosity, *args, **options):
        if verbosity > 1:
            logger.setLevel(logging.DEBUG)

        i_d = Import_Dyscyplin.objects.create(
            owner=get_user_model().objects.first(), rok=rok
        )

        i_d.plik.save(name=Path(path.name).name, content=File(path))

        logger.debug("Tworzę kolumny")
        stworz_kolumny.apply(args=(i_d.pk,))

        i_d = Import_Dyscyplin.objects.get(pk=i_d.pk)
        i_d.zatwierdz_kolumny()
        i_d.save()

        logger.debug("Analizuję plik")
        przeanalizuj_import_dyscyplin.apply(args=(i_d.pk,))

        logger.debug(
            "Poprawne wiersze:    %s" % i_d.poprawne_wiersze_do_integracji().count()
        )
        logger.debug("Niepoprawne wiersze: %s" % i_d.niepoprawne_wiersze().count())

        for elem in i_d.niepoprawne_wiersze().order_by("row_no"):
            logger.debug(
                f"{elem.row_no}: {elem.stan} {elem.info} {elem.nazwisko} {elem.imiona}"
            )

        logger.debug("Integruję plik")
        integruj_import_dyscyplin.apply(args=(i_d.pk,))

        i_d.delete()
