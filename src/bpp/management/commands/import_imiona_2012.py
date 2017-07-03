# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction
from bpp.management.commands import files_or_directory
from bpp.imports.egeria_2012 import importuj_imiona


class Command(BaseCommand):
    help = 'Importuje imiona do wydzialu z arkuszy XLS'
    args = '<katalog z xlsx> | <plik xls 1> <plik xls 2> ...'

    @transaction.atomic
    def handle(self, *args, **options):
        for plik in files_or_directory(args):
            print("==> ", plik)
            importuj_imiona(plik)