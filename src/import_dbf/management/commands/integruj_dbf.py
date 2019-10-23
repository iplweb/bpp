# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction

from import_dbf.util import integruj_wydzialy, integruj_jednostki, integruj_uczelnia, integruj_autorow


class Command(BaseCommand):
    help = 'Integruje zaimportowaną bazę DBF z bazą BPP'

    def add_arguments(self, parser):
        parser.add_argument("--uczelnia", type=str, default="Domyślna Uczelnia")
        parser.add_argument("--skrot", type=str, default="DU")

        parser.add_argument("--skip-wydzial", action="store_true")
        parser.add_argument("--skip-jednostka", action="store_true")
        parser.add_argument("--skip-autor", action="store_true")

    @transaction.atomic
    def handle(self, uczelnia, skrot, *args, **options):
        uczelnia = integruj_uczelnia(nazwa=uczelnia, skrot=skrot)

        if not options['skip_wydzial']:
            integruj_wydzialy(uczelnia)

        if not options['skip_jednostka']:
            integruj_jednostki(uczelnia)

        if not options['skip_autor']:
            integruj_autorow(uczelnia)
