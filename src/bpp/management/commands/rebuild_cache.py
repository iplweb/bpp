# -*- encoding: utf-8 -*-
import multiprocessing

from django.core.management import BaseCommand

from bpp.models.cache import Rekord
from bpp.tasks import aktualizuj_cache_rekordu


class Command(BaseCommand):
    help = 'Odbudowuje cache'


    def handle(self, *args, **options):
        from django import db
        db.connections.close_all()

        cpu_count = multiprocessing.cpu_count()
        num_proc = int(floor(cpu_count * 0.75)) or 1
        pool = multiprocessing.Pool(processes=num_proc)
        pool.starmap(self.rebuild, )

    def rebuild(self, offset=None, limit=None):
        for r in Rekord.objects.all()[offset:limit]:
            aktualizuj_cache_rekordu(r.original)
