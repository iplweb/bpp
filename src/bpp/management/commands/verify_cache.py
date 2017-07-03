# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Q
import psycopg2
import sys
from bpp.models import Rekord


class Command(BaseCommand):
    help = 'Weryfikuje prace bez autorow'

    @transaction.atomic
    def handle(self, *args, **options):
        connection = psycopg2.connect(database="b_med", host="linux-dev")
        cursor = connection.cursor()

        raise NotImplementedError("wybierz wszystkie rekordy BEZ autorow.")
        for praca in Rekord.objects.filter(Q(autorzy=[]) | Q(autorzy=None)):
            orig = praca.get_original_object()
            if getattr(orig, 'autorzy'):
                assert(orig.autorzy.count() == 0)
            else:
                assert(orig.autor == None)

            qry = "SELECT * FROM b_a WHERE idt = %s" % praca.object_pk
            cursor.execute(qry)
            res = cursor.fetchall()
            assert(len(res) == 0)
        print("%s: DB is correct!" % sys.argv[0])