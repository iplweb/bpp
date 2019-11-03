# -*- encoding: utf-8 -*-
import multiprocessing

from django.core.management import BaseCommand

from bpp.models import Wydawnictwo_Zwarte, Wydawnictwo_Ciagle, rebuild_ciagle, rebuild_zwarte
from bpp.util import partition_count, no_threads


class Command(BaseCommand):
    help = 'Odbudowuje cache'

    def handle(self, *args, **options):
        from django import db
        db.connections.close_all()

        pool_size = no_threads(0.75)
        pool = multiprocessing.Pool(processes=pool_size)

        pool.starmap(rebuild_ciagle, partition_count(Wydawnictwo_Ciagle.objects, pool_size))
        pool.starmap(rebuild_zwarte, partition_count(Wydawnictwo_Zwarte.objects, pool_size))
