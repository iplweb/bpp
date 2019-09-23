# -*- encoding: utf-8 -*-
import argparse

from django.core.management import BaseCommand
from django.db import transaction

from import_dbf.util import import_dbf


class Command(BaseCommand):
    help = 'Konwertuje plik DBF do zapytań SQLowych PostgreSQL'

    def add_arguments(self, parser):
        parser.add_argument("plik", nargs="+", type=argparse.FileType('rb'))

    @transaction.atomic
    def handle(self, plik, *args, **options):
        for plik in plik:
            print("-- plik: ", plik.name)
            import_dbf(plik.name)
