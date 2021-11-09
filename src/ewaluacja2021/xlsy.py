import os
from decimal import Decimal

import openpyxl
from django.db.models import Sum, Value

from ewaluacja2021.const import LATA_2017_2018, LATA_2019_2021
from ewaluacja2021.reports import get_data_for_report, write_data_to_report
from ewaluacja2021.util import autor2fn, output_table_to_xlsx

from bpp.models import Autor


class WyjsciowyXLSX:
    def __init__(self, title, rekordy, dane, katalog_wyjsciowy):
        self.title = title
        self.rekordy = rekordy
        self.dane = dane
        self.katalog_wyjsciowy = katalog_wyjsciowy

        self.create_workbook()

    def create_workbook(self):
        self.wb = openpyxl.Workbook()

    def initialize_worksheet(self):
        self.ws = self.wb.active
        if self.title:
            self.ws.title = self.title[:31]

    def tabelka(self):
        write_data_to_report(self.ws, get_data_for_report(self.rekordy))

    def get_output_name(self):
        return f"{self.title}.xlsx"

    def zapisz(self):
        self.wb.save(os.path.join(self.katalog_wyjsciowy, self.get_output_name()))

    def metka(self):
        raise NotImplementedError()

    def zrob(self):
        self.initialize_worksheet()
        self.metka()
        self.ws.append([])
        self.tabelka()
        self.zapisz()


class CalosciowyXLSX(WyjsciowyXLSX):
    def metka(self):
        self.ws.append(
            [
                "Parametry raportu 3N",
                "raport całościowy",
            ]
        )
        self.ws.append(["Stan na dzień/moment", self.dane["ostatnia_zmiana"]])
        self.ws.append(["Dyscyplina", self.dane["dyscyplina"]])
        self.ws.append(["Liczba N", self.dane["liczba_n"]])
        self.ws.append(["Liczba 0.8N", self.dane["liczba_0_8_n"]])
        self.ws.append(["Liczba 2.2N", self.dane["liczba_2_2_n"]])
        self.ws.append(["Liczba 3*N", Decimal("3.0") * self.dane["liczba_n"]])
        self.ws.append(
            [
                "Suma slotów za lata 2017-2018",
                self.dane["sumy_slotow"][LATA_2017_2018],
            ]
        )
        self.ws.append(
            [
                "Suma slotów za lata 2019-2021",
                self.dane["sumy_slotow"][LATA_2019_2021],
            ]
        )

        sumy = self.rekordy.filter(do_ewaluacji=True).aggregate(
            suma_slot=Sum("slot"), suma_pkdaut=Sum("pkdaut")
        )
        self.ws.append(["Zebrana suma slotów za wszystkie prace", sumy["suma_slot"]])
        self.ws.append(["Zebrana suma PKDAut za wszystkie prace", sumy["suma_pkdaut"]])


class WypelnienieXLSX(CalosciowyXLSX):
    def get_data_for_report(self):
        id_autorow = self.rekordy.values_list("autor_id", flat=True).distinct()
        for autor in Autor.objects.filter(pk__in=id_autorow):

            maks_pkt_aut_calosc = self.dane["maks_pkt_aut_calosc"].get(str(autor.pk))
            maks_pkt_aut_monografie = self.dane["maks_pkt_aut_monografie"].get(
                str(autor.pk)
            )

            sumy = self.rekordy.filter(do_ewaluacji=True, autor_id=autor.pk).aggregate(
                suma_slot=Sum("slot"),
                suma_pkdaut=Sum("pkdaut"),
            )

            sumy_monografie = self.rekordy.filter(
                do_ewaluacji=True, monografia=Value("t"), autor_id=autor.pk
            ).aggregate(
                suma_slot=Sum("slot"),
            )

            sumy_wszystkie = self.rekordy.filter(autor_id=autor.pk).aggregate(
                suma_pkdaut=Sum("pkdaut"),
            )

            yield [
                str(autor.id),
                autor.nazwisko + " " + autor.imiona,
                maks_pkt_aut_calosc,
                sumy["suma_slot"] or 0,
                (sumy["suma_slot"] or 0) / maks_pkt_aut_calosc,
                maks_pkt_aut_monografie,
                (sumy_monografie["suma_slot"] or 0),
                (sumy_monografie["suma_slot"] or 0) / maks_pkt_aut_calosc,
                sumy["suma_pkdaut"],
                sumy_wszystkie["suma_pkdaut"],
                (sumy["suma_pkdaut"] or 0) / (sumy_wszystkie["suma_pkdaut"] or 1),
            ]

    def write_data_to_report(self, ws: openpyxl.worksheet.worksheet.Worksheet, data):
        output_table_to_xlsx(
            ws,
            "Przeszly",
            [
                # "ID elementu",
                "ID autora",
                "Nazwisko i imię",
                #
                "Maksymalna suma udziałów",
                "Sprawozdana suma udziałów",
                "Procent sprawozdanej sumy udziałów",
                #
                "Maksymalna suma udziałów - monografie",
                "Sprawozdana suma udziałów - monografie",
                "Procent sprawozdanej sumy udziałów - monografie",
                #
                "PKDaut prac sprawozdanych",
                "PKDaut wszystkich prac",
                "Procent PKDaut sprawozdanych",
            ],
            data,
            first_column_url="https://{site_name}/bpp/autor/",
            column_widths={
                "A": 10,
                "B": 14,
                "C": 14,
                "D": 14,
                "E": 14,
                "F": 14,
                "G": 14,
                "H": 14,
                "I": 14,
                "J": 14,
                "K": 14,
                "L": 14,
            },
            autor_column_url=1,
        )

    def tabelka(self):
        dane = self.get_data_for_report()
        self.write_data_to_report(self.ws, dane)


class AutorskiXLSX(WyjsciowyXLSX):
    def __init__(self, autor, title, rekordy, dane, katalog_wyjsciowy):
        super().__init__(
            title=title, rekordy=rekordy, dane=dane, katalog_wyjsciowy=katalog_wyjsciowy
        )
        self.autor = autor

    def metka(self):
        self.ws.append(
            [
                "Parametry raportu 3N",
                "wyciąg dla pojedynczego autora",
            ]
        )
        self.ws.append(["Stan na dzień/moment", self.dane["ostatnia_zmiana"]])
        self.ws.append(["Dyscyplina", self.dane["dyscyplina"]])
        self.ws.append(
            [
                "Maks. suma slotów za wszytkie prace",
                self.dane["maks_pkt_aut_calosc"].get(str(self.autor.pk)),
            ]
        )

        sumy = self.rekordy.filter(do_ewaluacji=True).aggregate(
            suma_slot=Sum("slot"), suma_pkdaut=Sum("pkdaut")
        )
        self.ws.append(["Zebrana suma slotów za wszystkie prace", sumy["suma_slot"]])
        self.ws.append(["Zebrana suma PKDAut za wszystkie prace", sumy["suma_pkdaut"]])

        self.ws.append(
            [
                "Maks. suma slotów za monografie",
                self.dane["maks_pkt_aut_monografie"].get(str(self.autor.pk)),
            ]
        )

        sumy = self.rekordy.filter(do_ewaluacji=True, monografia=Value("t")).aggregate(
            suma_slot=Sum("slot"), suma_pkdaut=Sum("pkdaut")
        )

        self.ws.append(["Zebrana suma slotów za monografie", sumy["suma_slot"]])
        self.ws.append(["Zebrana suma PKDAut za monografie", sumy["suma_pkdaut"]])

    def get_output_name(self):
        return autor2fn(self.autor) + ".xlsx"
