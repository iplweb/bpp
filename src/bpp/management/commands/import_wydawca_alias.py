# -*- encoding: utf-8 -*-

import logging

import xlrd
from django.core.management import BaseCommand
from django.core.exceptions import ValidationError

from bpp.models import Wydawca

logger = logging.getLogger("django")


class Command(BaseCommand):
    help = "Importuje aliasy wydawców z pliku XLS (alias -> nazwa wydawcy)"

    def add_arguments(self, parser):
        parser.add_argument("plik")

    def handle(
        self, plik, verbosity, *args, **options,
    ):
        logger.setLevel(logging.WARNING)
        if verbosity > 1:
            logger.setLevel(logging.INFO)

        book = xlrd.open_workbook(plik)
        sheet = book.sheet_by_index(0)

        for row_idx in range(1, sheet.nrows):
            cells = sheet.row_slice(rowx=row_idx, start_colx=0, end_colx=2)
            alias, wydawca = [cell.value for cell in cells]

            try:
                w = Wydawca.objects.get(nazwa=wydawca.strip())
            except Wydawca.DoesNotExist:
                logger.info(f"{wydawca} zdefiniowany w pliku XLS nie istnieje")
                continue

            a = Wydawca.objects.get_or_create(nazwa=alias.strip())[0]

            if a.alias_dla != w:
                a.alias_dla = w
                try:
                    a.save()
                except ValidationError:
                    logger.warn(
                        f"** alias {alias} rozpoznany jako {a} to alias do samego siebie {w}, idę dalej"
                    )
                    continue
                logger.info(f"{w.nazwa} dopisuje alias {a.nazwa}")
            else:
                logger.info(f"{w.nazwa} już miał {a.nazwa}")
