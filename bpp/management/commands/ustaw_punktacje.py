# -*- encoding: utf-8 -*-
from optparse import make_option
import sys

from django.core.management import BaseCommand
from django.db import transaction
from django.test.utils import override_settings

from bpp.models.cache import Rekord
from bpp.models.zrodlo import Punktacja_Zrodla


class Command(BaseCommand):
    help = 'Ustawia punktacje dla niektorych typow prac'

    # option_list = BaseCommand.option_list + (
    #     make_option("--initial-offset", action="store", type="int", default=0),
    #     make_option("--skip", action="store", type="int", default=0),
    #     make_option("--pk", action="store", type="str", default=None)
    # )

    @transaction.atomic
    @override_settings(CELERY_ALWAYS_EAGER=True)
    def handle(self, *args, **options):
        fn = ['impact_factor', 'punkty_kbn', 'index_copernicus', 'punktacja_wewnetrzna']

        for praca in Rekord.objects.filter(
            rok__gt=2013,
            charakter_formalny__skrot="AC",
        ).exclude(
            typ_kbn__skrot="000",
        ).exclude(
            typ_kbn__skrot="PNP"
        ).exclude(
            typ_kbn__skrot="RC").only("content_type", "object_id"):

            original = praca.original

            try:
                pz = Punktacja_Zrodla.objects.get(
                        rok=original.rok,
                        zrodlo=original.zrodlo)
            except Punktacja_Zrodla.DoesNotExist:
                print "BRAK PUNKTACJI ZRODLA: ", original.zrodlo, original.rok

            for field in fn:
                setattr(original, field, getattr(pz, field))

            original.save()