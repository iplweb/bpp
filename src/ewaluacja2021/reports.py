import openpyxl.worksheet.worksheet
from django.db.models import BooleanField, Case, F, Value, When

from ewaluacja2021.core.util import NieArtykul
from ewaluacja2021.util import output_table_to_xlsx

from bpp.models import Cache_Punktacja_Autora_Query
from bpp.util import strip_html


def get_data_for_report(qset):
    return (
        [
            # elem.id,
            str(elem.rekord_id),
            elem.autor_id,
            strip_html(elem.rekord.tytul_oryginalny),
            elem.rok,
            f"{elem.autor.nazwisko} {elem.autor.imiona}",
            elem.dyscyplina.nazwa,
            elem.monografia,
            elem.do_ewaluacji,
            elem.pkdaut,
            elem.slot,
            elem.rekord.punkty_kbn,
        ]
        for elem in qset
    )


def write_data_to_report(ws: openpyxl.worksheet.worksheet.Worksheet, data):
    output_table_to_xlsx(
        ws,
        "Przeszly",
        [
            # "ID elementu",
            "ID rekordu",
            "ID autora",
            "Tytuł",
            "Rok",
            "Autor",
            "Nazwa dyscypliny",
            "Monografia?",
            "Do ewaluacji",
            "PKDAut",
            "Slot",
            "PK",
        ],
        data,
        totals=["PKDAut", "Slot"],
        column_widths={
            "A": 10,
            "B": 14,
            "E": 14,
        },
    )


def rekordy(dane):
    return (
        Cache_Punktacja_Autora_Query.objects.filter(
            pk__in=[x["id"] for x in dane["wejscie"]]
        )
        .annotate(
            monografia=NieArtykul(
                F("rekord__charakter_formalny__rodzaj_pbn"), output_field=BooleanField()
            ),
            rok=F("rekord__rok"),
            do_ewaluacji=Case(
                When(pk__in=dane["optimum"], then=Value(True, BooleanField())),
                default=Value(False, BooleanField()),
            ),
        )
        .select_related("rekord", "autor", "dyscyplina")
    )


def load_data(fobj):
    import simplejson

    return simplejson.load(fobj, use_decimal=True)
