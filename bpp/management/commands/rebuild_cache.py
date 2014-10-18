# -*- encoding: utf-8 -*-
from optparse import make_option

from django.core.management import BaseCommand
from django.db import transaction
import sys
from bpp.models import cache
from bpp.models.cache import Rekord


class Command(BaseCommand):
    help = 'Odbudowuje cache'

    option_list = BaseCommand.option_list + (
        make_option("--initial-offset", action="store", type="int", default=0),
        make_option("--skip", action="store", type="int", default=0),
        make_option("--pk", action="store", type="int", default=None)
    )

    def handle(self, *args, **options):

        skip = options['skip']
        for r in Rekord.objects.all()[options['initial_offset']:].only(
                "content_type_id", "object_id"):

            if skip > 0:
                skip -= 1
                continue

            r.original.zaktualizuj_cache()

            skip = options['skip']

