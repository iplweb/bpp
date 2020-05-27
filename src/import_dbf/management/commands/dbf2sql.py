# -*- encoding: utf-8 -*-
import argparse
import multiprocessing

from django.core.management import BaseCommand

from import_dbf.util import dbf2sql


class Command(BaseCommand):
    help = "Konwertuje plik DBF do zapytań SQLowych PostgreSQL"

    def add_arguments(self, parser):
        parser.add_argument("plik", nargs="+", type=argparse.FileType("rb"))
        parser.add_argument("--disable-multithreading", action="store_true")

    def handle(self, disable_multithreading, plik, *args, **options):
        if not disable_multithreading:
            p = multiprocessing.Pool(processes=multiprocessing.cpu_count())
            p.map(dbf2sql, [x.name for x in plik])
        else:
            for x in plik:
                dbf2sql(x.name)
