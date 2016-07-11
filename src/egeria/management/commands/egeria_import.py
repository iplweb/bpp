# -*- encoding: utf-8 -*-

import argparse, xlrd

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import BaseCommand
from django.db import transaction

from egeria.models import EgeriaImport, EgeriaRow


class Command(BaseCommand):
    help = "Przeprowadza import pliku wyjściowego z systemu Comarch Egeria"

    def add_arguments(self, parser):
        parser.add_argument('infile', type=argparse.FileType('rb'))

    @transaction.atomic
    def handle(self, *args, **options):

        parent = EgeriaImport.objects.create(created_by=None)
        parent.file = SimpleUploadedFile(options['infile'].name, options['infile'].read())
        parent.save()

        x = xlrd.open_workbook(parent.file.path)
        sheet = x.sheet_by_index(0)

        for nrow in range(5, sheet.nrows):
            # [number:1.0, text:u'dr n. med.', text:u'Kowalska', text:u'Oleg', text:u'12121200587', text:u'Adiunkt', text:u'II Katedra i Klinika Chirurgii Og\xf3lnej, Gastroenterologicznej i Nowotwor\xf3w Uk\u0142adu Pokarmowego', text:u'I Wydzia\u0142 Lekarski z Oddzia\u0142em Stomatologicznym']
            lp, tytul_stopien, nazwisko, imie, pesel_md5, stanowisko, nazwa_jednostki, wydzial = sheet.row(nrow)
            #
            EgeriaRow.objects.create(
                lp=lp,
                tytul_stopien=tytul_stopien,
                nazwisko=nazwisko,
                imie=imie,
                pesel_md5=pesel_md5,
                stanowisko=stanowisko,
                nazwa_jednostki=nazwa_jednostki,
                wydzial=wydzial
            )

        import ipdb; ipdb.set_trace()
        raise NotImplementedError
