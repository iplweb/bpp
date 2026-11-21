import logging

import xlrd
from django.core.management import BaseCommand

from bpp.models import Wydawca
from bpp.models.wydawca import Poziom_Wydawcy
from bpp.wersjonowanie import zarejestruj_utworzenie

logger = logging.getLogger("django")


def _pobierz_lub_utworz_wydawce(nazwa):
    w, utworzono = Wydawca.objects.get_or_create(nazwa=nazwa)
    if utworzono:
        zarejestruj_utworzenie(
            None, w, "Utworzono poleceniem manage.py import_wydawca_poziom."
        )
    return w


def _ustaw_poziom(w, poziom):
    for rok in [2017, 2018, 2019, 2020]:
        try:
            pw = w.poziom_wydawcy_set.get(rok=rok)
            if pw.poziom != poziom:
                pw.poziom = poziom
                pw.save()

        except Poziom_Wydawcy.DoesNotExist:
            w.poziom_wydawcy_set.create(rok=rok, poziom=poziom)


class Command(BaseCommand):
    help = "Importuje listę wydawców z pliku XLS (nazwa wydawcy -> poziom)"

    def add_arguments(self, parser):
        parser.add_argument("plik")
        parser.add_argument(
            "--proponuj-dodatkowych",
            action="store_true",
            help="""
                Dla każdego wydawcy (nazwy) proponuj ustawienie poziomów
                u dodatkowych wydawców, bazując na podobnym początku nazwy wydawcy
                """,
        )
        parser.add_argument(
            "--przypisuj-dodatkowych",
            action="store_true",
            help="""
                Dla każdego 'dodatkowego' wydawcy przypisz również poziomy wydawcy
                """,
        )

    def handle(
        self,
        plik,
        proponuj_dodatkowych,
        przypisuj_dodatkowych,
        verbosity,
        *args,
        **options,
    ):
        if verbosity > 1:
            logger.setLevel(logging.DEBUG)

        book = xlrd.open_workbook(plik)
        sheet = book.sheet_by_index(0)

        for row_idx in range(1, sheet.nrows):
            cells = sheet.row_slice(rowx=row_idx, start_colx=0, end_colx=2)
            wydawca, poziom = (cell.value for cell in cells)

            poziom = int(poziom)
            w = _pobierz_lub_utworz_wydawce(wydawca.strip())

            wydawcy_do_przypisania = [
                w,
            ]

            if proponuj_dodatkowych:
                nazwa_logged = False
                for dw in Wydawca.objects.filter(nazwa__istartswith=w.nazwa).exclude(
                    pk=w.pk
                ):
                    if not nazwa_logged:
                        logger.info(w.nazwa)
                        nazwa_logged = True
                    logger.info(f"-> pasuje też do {dw.nazwa}")

                    if przypisuj_dodatkowych:
                        wydawcy_do_przypisania.append(dw)

            for w in wydawcy_do_przypisania:
                _ustaw_poziom(w, poziom)
