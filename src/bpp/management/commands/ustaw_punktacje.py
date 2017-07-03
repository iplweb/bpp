# -*- encoding: utf-8 -*-
from optparse import make_option
import sys

from django.core.management import BaseCommand
from django.db import transaction
from django.test.utils import override_settings

from bpp.models.cache import Rekord
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
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
        # fn = ['impact_factor', 'punkty_kbn', 'index_copernicus', 'punktacja_wewnetrzna']
        fn = ['punkty_kbn',]

        for praca in Wydawnictwo_Ciagle.objects.filter(
            rok__gte=2016,
            charakter_formalny__skrot="AC",
            punkty_kbn__gt=0).only("pk", "punkty_kbn", "tytul_oryginalny", "zrodlo_id", "rok"):
            try:
                pz = Punktacja_Zrodla.objects.get(
                        rok=praca.rok,
                        zrodlo=praca.zrodlo_id)
            except Punktacja_Zrodla.DoesNotExist:
                print("BRAK PUNKTACJI ZRODLA: ", praca.zrodlo, praca.rok)
                continue

            ch = False
            for field in fn:
                v = getattr(praca, field)
                s = getattr(pz, field)
                if v != s:
                    setattr(praca, field, s)
                    ch = True
            if ch:
                print(praca.tytul_oryginalny)
                praca.save()