# SELECT
# 	id,
# 	rok,
# 	tytul_oryginalny,
# 	informacje,
# 	opis_bibliograficzny_cache,
# 	opis_bibliograficzny_zapisani_autorzy_cache
# FROM
# 	bpp_rekord_mat
# WHERE
# 	opis_bibliograficzny_cache LIKE '%W: pod red%';

# -*- encoding: utf-8 -*-
import argparse
import csv
import logging

import Levenshtein
from django.core.management import BaseCommand
from django.db import transaction
from openpyxl import load_workbook

from bpp.models import (
    Zrodlo,
    Rodzaj_Zrodla,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Ciagle,
    TO_REDAKTOR,
)


class Command(BaseCommand):
    help = "Wyrzuca 'pod red.' z pola informacje, gdy jest już redaktor"

    def wyrzuc_pod_red_z_informacji(self, klass):
        """
        :type klass: bpp.models.Wydawnictwo_Ciagle
        """

        for elem in klass.objects.filter(
            informacje__startswith="pod red.",
            opis_bibliograficzny_cache__contains="W: pod red.",
        ):
            parsed_informacje = [
                x.strip()
                for x in elem.informacje.replace("pod red.", "").strip().split(",")
            ]

            zapisani_autorzy = [
                x.zapisany_jako
                for x in elem.autorzy_set.filter(
                    typ_odpowiedzialnosci__typ_ogolny=TO_REDAKTOR
                )
            ]

            odleglosci = [
                Levenshtein.distance(za, pi)
                for za, pi in zip(zapisani_autorzy, parsed_informacje)
            ]

            yield (
                [
                    elem.pk,
                    elem.tytul_oryginalny,
                    elem.rok,
                    elem.informacje,
                    parsed_informacje,
                    zapisani_autorzy,
                    odleglosci,
                ]
            )

    @transaction.atomic
    def handle(self, *args, **options):
        f = open("res.csv", "w")
        writer = csv.writer(f)
        writer.writerow(
            [
                "PK",
                "Tytul",
                "Rok",
                "Informacje",
                "Informacje przeanalizowane",
                "zapisani autorzy",
                "odleglosci",
            ]
        )
        for elem in Wydawnictwo_Zwarte, Wydawnictwo_Ciagle:
            for res in self.wyrzuc_pod_red_z_informacji(elem):
                writer.writerow(res)

        f.close()
