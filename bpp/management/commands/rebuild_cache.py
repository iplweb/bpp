# -*- encoding: utf-8 -*-
from optparse import make_option
import sys

from django.core.management import BaseCommand

from bpp.models.cache import Rekord


class Command(BaseCommand):
    help = 'Odbudowuje cache'

    option_list = BaseCommand.option_list + (
        make_option("--initial-offset", action="store", type="int", default=0),
        make_option("--skip", action="store", type="int", default=0),
        make_option("--pk", action="store", type="str", default=None)
    )

    def handle(self, *args, **options):
        if options['pk']:
            Rekord.objects.get(pk=options['pk']).original.zaktualizuj_cache()
            sys.exit(0)

        skip = options['skip']
        for r in Rekord.objects.all()[options['initial_offset']:].only(
                "content_type_id", "object_id"):

            if skip > 0:
                skip -= 1
                continue

            r.original.zaktualizuj_cache()

            skip = options['skip']

