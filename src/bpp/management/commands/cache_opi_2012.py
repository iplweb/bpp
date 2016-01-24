# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction
from bpp.models import Opi_2012_Tytul_Cache


class Command(BaseCommand):
    help = "Keszuje tytuly prac"

    @transaction.atomic
    def handle(self, *args, **options):
        Opi_2012_Tytul_Cache.objects.rebuild()