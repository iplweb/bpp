from __future__ import annotations

import logging
import operator
from functools import reduce

import openpyxl
from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Q
from flexible_reports.models import Datasource
from openpyxl.styles import Alignment

from import_common.normalization import normalize_filename

from bpp.models import Jednostka, Rekord, Wydzial
from bpp.util import pbar, worksheet_columns_autosize, worksheet_create_table

logger = logging.getLogger("django")


class Command(BaseCommand):
    help = (
        "Polecenie generuje skoroszyty XLSX, po jednym dla każdej jednostki, nazwane od nazw jednostek, "
        "przydzielając prace do plików wg pierwszego afiliowanego autora, z pracami wg zapytań odpowiadających "
        "zapytaniom z raportu wydziałów (flexible_reports/datasources) dla działu 1.x oraz 2.x tych zapytań, dodatkowo "
        "doklejając do skoroszytów kolumny dotyczące opłat za publikacje, do wypełnienia przez kierowników "
        "jednostek. "
    )

    @transaction.atomic
    def handle(self, **options):
        datasources: [Datasource] = (
            Datasource.objects.filter(
                Q(label__startswith="1.1")
                | Q(label__startswith="1.2")
                | Q(label__startswith="2.1")
                | Q(label__startswith="2.3")
            )
            .exclude(label__endswith="jednostka")
            .exclude(label__endswith="autor")
        )

        queries = []
        for wydzial in Wydzial.objects.all():

            class FakeObj:
                pk = wydzial.pk

            for datasource in datasources:
                queries.append(datasource.get_filter({"obiekt": FakeObj()}))

        rekordy = (
            Rekord.objects.filter(reduce(operator.or_, queries))
            .filter(rok__gte=2020)
            .distinct()
        )

        pierwszy_autor_afiliowany = {
            rekord.pk: rekord.pierwszy_autor_afiliowany
            for rekord in rekordy
            if rekord.pierwszy_autor_afiliowany is not None
        }

        jednostki_ids = Jednostka.objects.filter(
            pk__in={paa.jednostka_id for paa in pierwszy_autor_afiliowany.values()}
        ).values_list("pk", flat=True)

        for jednostka_id in pbar(jednostki_ids):
            rekordy_jednostki = rekordy.filter(
                autorzy__pk__in=[
                    paa.pk
                    for paa in pierwszy_autor_afiliowany.values()
                    if paa.jednostka_id == jednostka_id
                ]
            ).order_by("-rok")

            wb = openpyxl.Workbook()
            s = wb.worksheets[0]
            s.append(
                [
                    "Tytuł oryginalny",
                    "ID rekordu",
                    "Rok",
                    "Pierwszy autor afiliowany",
                    "Publikacja bezkosztowa (brak kosztów zewnętrznych\nlub wydawnictwo własne): tak/nie",
                    "Środki finansowe, o których mowa w artykule 365 pkt 2\nustawy (subwencja, w tym rezerwa "
                    "rektora, dziekana,\nopen acess): tak/nie",
                    "Środki finansowe na realizację projektu: tak/nie\n (środki finansowe przyznane na realizację "
                    "projektu\nw zakresie badan naukowych\n lub prac rozwojowych)",
                    "Inne środki finansowe (np. prace \nzlecone): tak/nie",
                    "Kwota (zł brutto)",
                ]
            )

            for rekord in rekordy_jednostki:
                s.append(
                    [
                        rekord.tytul_oryginalny,
                        str(rekord.pk),
                        rekord.rok,
                        str(pierwszy_autor_afiliowany[rekord.id].autor),
                    ]
                )

            worksheet_create_table(s)
            worksheet_columns_autosize(s, max_width=80, multiplier=1.0)

            for row in s:
                for cell in row:
                    cell.alignment = Alignment(wrapText=True)
                    cell.value = cell.value
                break

            c = s["B2"]
            s.freeze_panes = c

            wb.save(
                normalize_filename(Jednostka.objects.get(pk=jednostka_id).nazwa)
                + ".xlsx"
            )
