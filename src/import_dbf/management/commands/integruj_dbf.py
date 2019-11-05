# -*- encoding: utf-8 -*-
import multiprocessing
from math import floor

import django

django.setup()
from django.core.management import BaseCommand

from bpp.models import Konferencja
from import_dbf.models import Bib, B_A
from import_dbf.util import integruj_wydzialy, integruj_jednostki, integruj_uczelnia, integruj_autorow, \
    integruj_publikacje, integruj_charaktery, integruj_jezyki, integruj_kbn, integruj_zrodla, integruj_b_a, \
    wyswietl_prace_bez_dopasowania, usun_podwojne_przypisania_b_a, integruj_tytuly_autorow, \
    integruj_funkcje_autorow, mapuj_elementy_publikacji, ekstrakcja_konferencji, przypisz_jednostki, \
    sprawdz_zamapowanie_autorow
from bpp.util import partition_count
import logging


class Command(BaseCommand):
    help = 'Integruje zaimportowaną bazę DBF z bazą BPP'

    def add_arguments(self, parser):
        parser.add_argument("--uczelnia", type=str, default="Domyślna Uczelnia")
        parser.add_argument("--skrot", type=str, default="DU")

        parser.add_argument("--enable-all", action="store_true")
        parser.add_argument("--disable-transaction", action="store_true")

        parser.add_argument("--enable-wydzial", action="store_true")
        parser.add_argument("--enable-jednostka", action="store_true")
        parser.add_argument("--enable-autor", action="store_true")
        parser.add_argument("--enable-publikacja", action="store_true")
        parser.add_argument("--enable-charakter-kbn-jezyk", action="store_true")
        parser.add_argument("--enable-zrodlo", action="store_true")
        parser.add_argument("--enable-b-a", action="store_true")
        parser.add_argument("--enable-przypisz-jednostki", action="store_true")

    def handle(self, uczelnia, skrot, enable_all, disable_transaction, *args, **options):
        verbosity = int(options['verbosity'])
        logger = logging.getLogger("main")
        if verbosity > 1:
            logger.setLevel(logging.DEBUG)

        from django import db
        db.connections.close_all()

        cpu_count = multiprocessing.cpu_count()
        num_proc = int(floor(cpu_count * 0.875)) or 1
        pool = multiprocessing.Pool(processes=num_proc)

        pool.apply(integruj_uczelnia, (uczelnia, skrot))

        if enable_all or options['enable_wydzial']:
            logger.debug("Wydzialy")
            pool.apply(integruj_wydzialy)

        if enable_all or options['enable_jednostka']:
            logger.debug("Jednostki")
            pool.apply(integruj_jednostki)

        if enable_all or options['enable_autor']:
            pool.apply(integruj_tytuly_autorow)
            pool.apply(integruj_funkcje_autorow)

            # 'Jose Miguel', 'Caldas' <==> 'Jose', 'Miguel Caldas'
            # with fuj as (select imiona || ' ' || nazwisko as x, idt_aut as y from import_dbf_aut where exp_id = idt_aut) select x, array_agg(y) from fuj group by x having count(*) > 1

            logger.debug("Autorzy")
            pool.apply(integruj_autorow)
            logger.debug("Sprawdzam czy wszyscy sa przypisani")
            pool.apply(sprawdz_zamapowanie_autorow)

        if enable_all or options['enable_charakter_kbn_jezyk']:
            pool.apply(integruj_charaktery)
            pool.apply(integruj_kbn)
            pool.apply(integruj_jezyki)

        if enable_all or options['enable_zrodlo']:
            logger.debug("Zrodla")
            pool.apply(integruj_zrodla)

        if enable_all or options['enable_publikacja']:
            logger.debug("Publikacje - wyciągam dane")

            pool.starmap(mapuj_elementy_publikacji, partition_count(
                Bib.objects.exclude(analyzed=True), num_proc))

            logger.info("Integruje konferencje")
            if Konferencja.objects.count() < 100:
                pool.apply(ekstrakcja_konferencji)

            logger.info("Integruje publikacje")
            pool.starmap(integruj_publikacje, partition_count(
                Bib.objects.filter(object_id=None, analyzed=True), num_proc))

            pool.apply(wyswietl_prace_bez_dopasowania, (logger,))

        if enable_all or options['enable_b_a']:
            logger.info("Usuwanie podwojnych przypisan")
            pool.apply(usun_podwojne_przypisania_b_a, (logger,))
            logger.debug("Integracja B_A")
            pool.starmap(integruj_b_a, partition_count(B_A.objects, num_proc))
            logger.debug("Przypisuje jednostki do autorow")

        if enable_all or options['enable_przypisz_jednostki']:
            logger.debug("Przypisuje Autor_Jednostka masowo")
            pool.apply(przypisz_jednostki)
