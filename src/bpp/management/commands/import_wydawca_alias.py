# -*- encoding: utf-8 -*-

import logging

import xlrd
from django.core.management import BaseCommand

from bpp.models import Wydawca

logger = logging.getLogger("django")


class Command(BaseCommand):
    help = "Importuje aliasy wydawców z pliku XLS (alias -> nazwa wydawcy)"

    def add_arguments(self, parser):
        parser.add_argument("plik")

    def handle(
        self, plik, verbosity, *args, **options,
    ):
        if verbosity > 1:
            logger.setLevel(logging.DEBUG)

        book = xlrd.open_workbook(plik)
        sheet = book.sheet_by_index(0)

        for row_idx in range(1, sheet.nrows):
            cells = sheet.row_slice(rowx=row_idx, start_colx=0, end_colx=2)
            alias, wydawca = [cell.value for cell in cells]

            try:
                w = Wydawca.objects.get(nazwa=wydawca.strip())
            except Wydawca.DoesNotExist:
                logger.debug(f"{wydawca} zdefiniowany w pliku XLS nie istnieje")
                continue

            alias = Wydawca.objects.get_or_create(nazwa=alias.strip())[0]

            if alias.alias_dla != w:
                alias.alias_dla = w
                alias.save()
                logger.debug(f"{w.nazwa} dopisuje alias {alias.nazwa}")
            else:
                logger.debug(f"{w.nazwa} już miał {alias.nazwa}")
