# -*- encoding: utf-8 -*-
import multiprocessing

from django.conf import settings
from django.core.management import BaseCommand

from bpp.models import (
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
    Patent,
    rebuild_ciagle,
    rebuild_zwarte,
    rebuild_patent,
)
from bpp.util import no_threads, partition_count


def subprocess_setup(*args):
    from django.db import connection

    connection.connect()


class Command(BaseCommand):
    help = "Odbudowuje cache"

    def handle(self, *args, **options):
        if not settings.TESTING:
            from django import db

            db.connections.close_all()

        pool_size = no_threads(0.75)
        pool = multiprocessing.Pool(processes=pool_size, initializer=subprocess_setup)

        pc = pool.apply(partition_count, args=(Wydawnictwo_Ciagle.objects, pool_size))
        pool.starmap(rebuild_ciagle, pc)

        pc = pool.apply(partition_count, args=(Wydawnictwo_Zwarte.objects, pool_size))
        pool.starmap(rebuild_zwarte, pc)

        pc = pool.apply(partition_count, args=(Patent.objects, pool_size))
        pool.starmap(rebuild_patent, pc)
