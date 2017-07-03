# -*- encoding: utf-8 -*-
from optparse import make_option
import sys

from django.core.management import BaseCommand
from django.db import transaction

from bpp.models.cache import Rekord
from bpp.models import Autor, Autorzy

class Command(BaseCommand):
    help = 'Kasuje autorow bez prac'

    @transaction.atomic
    def handle(self, *args, **options):
        for a in Autor.objects.all().only("id"):
            res = Autorzy.objects.filter(autor_id=a.pk)[:1]
            if res.count() == 0:
                print("BRAK PRAC: ID=%s, autor=%s, USUWAM!" % (a.pk, str(a)))
                a.delete()