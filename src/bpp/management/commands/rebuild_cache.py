# -*- encoding: utf-8 -*-
from optparse import make_option
import sys

from django.core.management import BaseCommand

from bpp.models.cache import Rekord


class Command(BaseCommand):
    help = 'Odbudowuje cache'

    def handle(self, *args, **options):
        for r in Rekord.objects.all().only("content_type_id", "object_id"):
            r.original.zaktualizuj_cache()