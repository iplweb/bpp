import os
from argparse import FileType

from django.core.management import BaseCommand

from ewaluacja2021.reports import load_data, rekordy
from ewaluacja2021.util import autor2fn
from ewaluacja2021.xlsy import AutorskiXLSX, CalosciowyXLSX, WypelnienieXLSX

from bpp.models import Autor
from bpp.util import pbar


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("wejscie", type=FileType("r"))
        parser.add_argument("--katalog-wyjsciowy", type=str, default=None)

    def handle(self, wejscie, katalog_wyjsciowy, liczba_n=None, *args, **options):

        dane = load_data(wejscie)

        if katalog_wyjsciowy is None:
            katalog_wyjsciowy = wejscie.name.replace(".json", "_output")

        if not os.path.exists(katalog_wyjsciowy):
            os.mkdir(katalog_wyjsciowy)

        rekordy_danych = rekordy(dane)

        WypelnienieXLSX(
            "AAA_wypelnienie_slotow",
            rekordy=rekordy_danych,
            dane=dane,
            katalog_wyjsciowy=katalog_wyjsciowy,
        ).zrob()

        CalosciowyXLSX(
            "AAA_rekordy",
            rekordy=rekordy_danych,
            dane=dane,
            katalog_wyjsciowy=katalog_wyjsciowy,
        ).zrob()

        for autor in pbar(
            Autor.objects.filter(pk__in=(x.autor_id for x in rekordy(dane))),
            label="Dane autorow...",
        ):
            rekordy_autora = rekordy_danych.filter(autor_id=autor.id)
            AutorskiXLSX(
                autor=autor,
                title=autor2fn(autor),
                rekordy=rekordy_autora,
                dane=dane,
                katalog_wyjsciowy=katalog_wyjsciowy,
            ).zrob()
