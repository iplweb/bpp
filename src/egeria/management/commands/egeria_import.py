# -*- encoding: utf-8 -*-
import sys

from bpp.models.struktura import Uczelnia

reload(sys)
sys.setdefaultencoding("utf-8")

import argparse

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import BaseCommand
from django.db import transaction

from egeria.models import EgeriaImport


class Command(BaseCommand):
    help = "Przeprowadza import pliku wyjściowego z systemu Comarch Egeria"

    def add_arguments(self, parser):
        parser.add_argument('infile', type=argparse.FileType('rb'))

    @transaction.atomic
    def handle(self, *args, **options):
        parent = EgeriaImport.objects.create(created_by=None, uczelnia=Uczelnia.objects.all().first())
        parent.file = SimpleUploadedFile(options['infile'].name, options['infile'].read())
        parent.save()
        parent.everything(cleanup=False)
        # for elem in parent.unmatched():
        #     print elem.nazwisko, elem.imie
        parent.cleanup()