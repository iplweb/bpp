# -*- encoding: utf-8 -*-
from datetime import date

import os

from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import Autor_Jednostka

from bpp.imports.egeria_2012 import importuj_afiliacje
from bpp.imports.uml import UML_Egeria_2012_Mangle
from bpp.management.commands import files_or_directory

class Command(BaseCommand):
    help = 'Importuje afiliacje do wydziału z arkuszy XLS'
    args = '<katalog z xlsx> | <plik xls 1> <plik xls 2> ...'

    @transaction.atomic
    def handle(self, *args, **options):

        for plik_xls in files_or_directory(args):
            print((" *** Importuje plik", plik_xls))
            importuj_afiliacje(plik_xls, UML_Egeria_2012_Mangle)

        for aj in Autor_Jednostka.objects.filter(zakonczyl_prace=date(2012,12,31)):
            # Zakładamy, że ci ludzie pracują NADAL
            aj.zakonczyl_prace=None
            aj.save()
