# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction
from bpp import models
from bpp.management.post_syncdb import load_customized_sql


class Command(BaseCommand):
    help = 'Wczytuje plik custom.sql do bazy danych'

    @transaction.atomic
    def handle(self, **kwargs):
        load_customized_sql(models, [])