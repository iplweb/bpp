# -*- encoding: utf-8 -*-
import argparse
import logging
import multiprocessing
from math import floor

import django
from django.core.management import BaseCommand

import miniblog
from bpp.util import partition_count
from import_dbf.models import B_A, Bib
from import_dbf.util import (
    integruj_autorow,
    integruj_b_a,
    integruj_charaktery,
    integruj_funkcje_autorow,
    integruj_jednostki,
    integruj_jezyki,
    integruj_kbn,
    integruj_publikacje,
    integruj_tytuly_autorow,
    integruj_uczelnia,
    integruj_wydzialy,
    integruj_zrodla,
    mapuj_elementy_publikacji,
    przypisz_jednostki,
    sprawdz_zamapowanie_autorow,
    usun_podwojne_przypisania_b_a,
    wyswietl_prace_bez_dopasowania,
    wzbogacaj_charaktery,
    zatwierdz_podwojne_przypisania,
    dodaj_aktualnosc,
    set_sequences,
    przypisz_grupy_punktowe,
)

django.setup()


class Command(BaseCommand):
    help = "Integruje zaimportowaną bazę DBF z bazą BPP"

    def add_arguments(self, parser):
        parser.add_argument("--uczelnia", type=str, default="Domyślna Uczelnia")
        parser.add_argument("--skrot", type=str, default="DU")

        parser.add_argument("--disable-multithreading", action="store_true")

        parser.add_argument("--enable-all", action="store_true")
        parser.add_argument("--disable-transaction", action="store_true")

        parser.add_argument("--enable-wydzial", action="store_true")
        parser.add_argument("--enable-jednostka", action="store_true")
        parser.add_argument("--enable-autor", action="store_true")
        parser.add_argument("--enable-publikacja", action="store_true")
        parser.add_argument("--enable-grupy-punktowe", action="store_true")

        parser.add_argument("--enable-mapuj-publikacja", action="store_true")
        parser.add_argument("--enable-charakter-kbn-jezyk", action="store_true")
        parser.add_argument(
            "--charaktery-enrichment-xls", type=argparse.FileType("rb"), nargs="+"
        )

        parser.add_argument("--enable-zrodlo", action="store_true")
        parser.add_argument("--enable-b-a", action="store_true")
        parser.add_argument(
            "--enable-zatwierdz-podwojne-przypisania",
            action="store_true",
            help="""W przypadku, gdyby podwójne przypisania w bazie danych były OK, podaj ten argument
            aby utworzyć dodatkowe rekordy dla prawidłowo zdublowanych autorów""",
        )
        parser.add_argument("--enable-przypisz-jednostki", action="store_true")
        parser.add_argument("--enable-dodaj-aktualnosc", action="store_true")

    def handle(
        self,
        uczelnia,
        skrot,
        enable_all,
        disable_transaction,
        disable_multithreading,
        *args,
        **options
    ):
        verbosity = int(options["verbosity"])
        logger = logging.getLogger("django")
        if verbosity > 1:
            logger.setLevel(logging.DEBUG)

        from django import db

        db.connections.close_all()

        cpu_count = multiprocessing.cpu_count()
        num_proc = int(floor(cpu_count * 0.875)) or 1
        pool = multiprocessing.Pool(processes=num_proc)

        if disable_multithreading:

            def apply(fun, args):
                return fun(*args)

            pool.apply = apply

            def starmap(fun, lst):
                for elem in lst:
                    fun(*elem)

            pool.starmap = starmap

        pool.apply(integruj_uczelnia, (uczelnia, skrot))

        if enable_all or options["enable_wydzial"]:
            logger.debug("Wydzialy")
            pool.apply(integruj_wydzialy)

        if enable_all or options["enable_jednostka"]:
            logger.debug("Jednostki")
            pool.apply(integruj_jednostki)

        if enable_all or options["enable_autor"]:
            pool.apply(integruj_tytuly_autorow)
            pool.apply(integruj_funkcje_autorow)

            # 'Jose Miguel', 'Caldas' <==> 'Jose', 'Miguel Caldas'
            # with fuj as (select imiona || ' ' || nazwisko as x, idt_aut as y
            # from import_dbf_aut where exp_id = idt_aut) select x, array_agg(y)
            # from fuj group by x having count(*) > 1

            logger.debug("Autorzy")
            pool.apply(integruj_autorow)
            logger.debug("Sprawdzam czy wszyscy sa przypisani")
            pool.apply(sprawdz_zamapowanie_autorow)

        if enable_all or options["enable_charakter_kbn_jezyk"]:
            pool.apply(integruj_charaktery)

            fp = options.get("charaktery_enrichment_xls")
            if fp:
                pool.apply(wzbogacaj_charaktery, args=(fp[0].name,))

            pool.apply(integruj_kbn)
            pool.apply(integruj_jezyki)

        if enable_all or options["enable_zrodlo"]:
            logger.debug("Zrodla")
            pool.apply(integruj_zrodla)

        if enable_all or options["enable_mapuj_publikacja"]:
            logger.debug("Publikacje - wyciągam dane")

            pool.starmap(
                mapuj_elementy_publikacji,
                partition_count(Bib.objects.exclude(analyzed=True), num_proc),
            )

        if enable_all or options["enable_publikacja"]:
            logger.info("Integruje publikacje")
            pool.starmap(
                integruj_publikacje,
                partition_count(
                    Bib.objects.filter(object_id=None, analyzed=True), num_proc
                ),
            )

            pool.apply(wyswietl_prace_bez_dopasowania, (logger,))
            pool.apply(set_sequences)

        if enable_all or options["enable_grupy_punktowe"]:
            pool.apply(przypisz_grupy_punktowe)

        if enable_all or options["enable_zatwierdz_podwojne_przypisania"]:
            logger.debug("Zatwierdzanie podwójnych podwojnych przypisan")
            pool.apply(zatwierdz_podwojne_przypisania, (logger,))

        if enable_all or options["enable_b_a"]:
            logger.debug("Usuwanie podwojnych przypisan")
            pool.apply(usun_podwojne_przypisania_b_a, (logger,))
            logger.debug("Integracja B_A")
            pool.starmap(integruj_b_a, partition_count(B_A.objects, num_proc))
            logger.debug("Przypisuje jednostki do autorow")

        if enable_all or options["enable_przypisz_jednostki"]:
            logger.debug("Przypisuje Autor_Jednostka masowo")
            pool.apply(przypisz_jednostki)

        if enable_all or options["enable_dodaj_aktualnosc"]:
            pool.apply(dodaj_aktualnosc)
