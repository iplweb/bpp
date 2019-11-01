# -*- encoding: utf-8 -*-
import multiprocessing
from math import floor

from django.core.management import BaseCommand
from django.db import transaction

from bpp.models.cache import Rekord
from bpp.tasks import aktualizuj_cache_rekordu
from import_dbf.util import partition_count


@transaction.atomic
def rebuild(offset=None, limit=None):
    print(offset, limit)
    ids = Rekord.objects.all()[offset:limit].values_list('pk')
    for r in Rekord.objects.filter(pk__in=ids).select_for_update():
        aktualizuj_cache_rekordu(r.original)


class Command(BaseCommand):
    help = 'Odbudowuje cache'

    def handle(self, *args, **options):
        from django import db
        db.connections.close_all()

        cpu_count = multiprocessing.cpu_count()
        num_proc = int(floor(cpu_count * 0.75)) or 1
        pool = multiprocessing.Pool(processes=num_proc)
        pool.starmap(rebuild, partition_count(Rekord.objects.all(), num_proc))
