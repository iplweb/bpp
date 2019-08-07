# -*- encoding: utf-8 -*-

import xlrd
from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import Wydawca
from bpp.models.wydawca import Poziom_Wydawcy


class Command(BaseCommand):
    help = 'Importuje listę wydawców z pliku XLS (nazwa wydawcy -> poziom)'

    def add_arguments(self, parser):
        parser.add_argument("plik")

    #@transaction.atomic
    def handle(self, *args, **options):
        book = xlrd.open_workbook(options['plik'])
        sheet = book.sheet_by_index(0)

        for row_idx in range(1, sheet.nrows):
            cells = sheet.row_slice(rowx=row_idx, start_colx=0, end_colx=2)
            wydawca, poziom = [cell.value for cell in cells]

            poziom = int(poziom)
            print(wydawca)
            w = Wydawca.objects.get_or_create(nazwa=wydawca.strip())[0]
            for rok in [2017, 2018, 2019, 2020]:
                try:
                    pw = w.poziom_wydawcy_set.get(rok=rok)
                    if pw.poziom != poziom:
                        pw.poziom = poziom
                        pw.save()

                except Poziom_Wydawcy.DoesNotExist:
                    w.poziom_wydawcy_set.create(rok=rok, poziom=poziom)
