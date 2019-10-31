# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction

from import_dbf.util import integruj_wydzialy, integruj_jednostki, integruj_uczelnia, integruj_autorow, \
    integruj_publikacje, integruj_charaktery, integruj_jezyki, integruj_kbn, integruj_zrodla, integruj_b_a, \
    wyswietl_prace_bez_dopasowania


class Command(BaseCommand):
    help = 'Integruje zaimportowaną bazę DBF z bazą BPP'

    def add_arguments(self, parser):
        parser.add_argument("--uczelnia", type=str, default="Domyślna Uczelnia")
        parser.add_argument("--skrot", type=str, default="DU")

        parser.add_argument("--disable-all", action="store_true")

        parser.add_argument("--enable-wydzial", action="store_true")
        parser.add_argument("--enable-jednostka", action="store_true")
        parser.add_argument("--enable-autor", action="store_true")
        parser.add_argument("--enable-publikacja", action="store_true")
        parser.add_argument("--enable-charakter-kbn-jezyk", action="store_true")
        parser.add_argument("--enable-zrodlo", action="store_true")
        parser.add_argument("--enable-b-a", action="store_true")

    @transaction.atomic
    def handle(self, uczelnia, skrot, disable_all, *args, **options):
        uczelnia = integruj_uczelnia(nazwa=uczelnia, skrot=skrot)

        if not disable_all or options['enable_wydzial']:
            integruj_wydzialy(uczelnia)

        if not disable_all or options['enable_jednostka']:
            integruj_jednostki(uczelnia)

        if not disable_all or options['enable_autor']:
            integruj_autorow(uczelnia)

        if not disable_all or options['enable_charakter_kbn_jezyk']:
            integruj_charaktery()
            integruj_kbn()
            integruj_jezyki()

        if not disable_all or options['enable_zrodlo']:
            integruj_zrodla()

        if not disable_all or options['enable_publikacja']:
            from bpp.models import cache
            cache.disable()
            integruj_publikacje()

        wyswietl_prace_bez_dopasowania()

        if not disable_all or options['enable_b_a']:
            from bpp.models import cache
            cache.disable()
            from django.conf import settings
            setattr(settings, 'ENABLE_DATA_AKT_PBN_UPDATE', False)
            integruj_b_a()
