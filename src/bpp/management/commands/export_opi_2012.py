# -*- encoding: utf-8 -*-
import os
import sys
import shutil

from django.core.management import BaseCommand
from django.db import transaction

from bpp.reports.opi_2012 import make_report_zipfile


class Command(BaseCommand):
    help = 'Eksportuje raporty OPI 2009-2012'

    @transaction.atomic
    def handle(self, *args, **options):
        wydzialy = ['1WL', '2WL', 'WF', 'WP']
        zipname = make_report_zipfile(wydzialy=wydzialy)

        if sys.platform == 'win32':
            shutil.move(
                zipname,
                os.path.join(os.getenv("USERPROFILE"), 'Desktop'))

