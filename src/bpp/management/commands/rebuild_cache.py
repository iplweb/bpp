# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand

from bpp.models.cache import Rekord


class Command(BaseCommand):
    help = 'Odbudowuje cache'

    def add_arguments(self, parser):
        parser.add_argument("--initial-offset", action="store", type=int,
                            default=0)
        parser.add_argument("--skip", action="store", type=int, default=0)

    def handle(self, *args, **options):
        qset = Rekord.objects.all()[options['initial_offset']:]

        # .filter(
        #     Q(opis_bibliograficzny_cache='') |
        #     Q(opis_bibliograficzny_autorzy_cache=[]))
        # | Q(opis_bibliograficzny_zapisani_autorzy_cache="")

        action = True
        for r in qset:
            if action:
                r.original.zaktualizuj_cache()
                action = False
                skip = options['skip'] + 1

            skip -= 1
            if skip == 0:
                action = True
