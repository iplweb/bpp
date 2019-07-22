# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand

from bpp import tasks


class Command(BaseCommand):
    help = 'Weryfikuje prace bez autorow'

    def handle(self, *args, **options):
        import psycopg2.extensions
        import select
        from django.db import connection

        crs = connection.cursor()  # get the cursor and establish the connection.connection
        pg_con = connection.connection
        pg_con.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        crs.execute('LISTEN cachequeue');

        print("Waiting for notifications on channel 'CACHEQUEUE'")
        while 1:
            if select.select([pg_con], [], [], None) == ([], [], []):
                print("Timeout")
            else:
                pg_con.poll()
                while pg_con.notifies:
                    notify = pg_con.notifies.pop()
                    tasks.aktualizuj_cache.delay()
