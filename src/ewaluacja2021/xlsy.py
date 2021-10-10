import os

import openpyxl
from django.db.models import Sum, Value

from ewaluacja2021.core import (
    DEFAULT_MAX_SLOT_AUT,
    DEFAULT_MAX_SLOT_MONO,
    LATA_2017_2018,
    LATA_2019_2021,
)
from ewaluacja2021.reports import get_data_for_report, write_data_to_report
from ewaluacja2021.util import autor2fn


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


class AutorskiXLSX(WyjsciowyXLSX):
    def __init__(self, autor, title, rekordy, dane, katalog_wyjsciowy):
        super(AutorskiXLSX, self).__init__(
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
                self.dane["maks_pkt_aut_calosc"].get(
                    self.autor.pk, DEFAULT_MAX_SLOT_AUT
                ),
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
                self.dane["maks_pkt_aut_monografie"].get(
                    self.autor.pk, DEFAULT_MAX_SLOT_MONO
                ),
            ]
        )

        sumy = self.rekordy.filter(do_ewaluacji=True, monografia=Value("t")).aggregate(
            suma_slot=Sum("slot"), suma_pkdaut=Sum("pkdaut")
        )

        self.ws.append(["Zebrana suma slotów za monografie", sumy["suma_slot"]])
        self.ws.append(["Zebrana suma PKDAut za monografie", sumy["suma_pkdaut"]])

    def get_output_name(self):
        return autor2fn(self.autor) + ".xlsx"
