# Create your models here.
import xlrd
from django.contrib.postgres.fields import JSONField
from django.db import models

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.exceptions import BłądDanychWejściowych
from integrator2.util import find_header_row
from long_running.asgi_notification_mixin import ASGINotificationMixin
from long_running.models import Operation


class ImportPracownikow(ASGINotificationMixin, Operation):
    plik_xls = models.FileField()

    def perform(self):
        xl_workbook = xlrd.open_workbook(self.plik_xls.path)

        for sheet in xl_workbook.sheets():
            n = find_header_row(sheet, "numer")
            if n is None:
                raise BłądDanychWejściowych(
                    "Brak poprawnego wiersza nagłówkowego. Porównaj importowane dane z przykładowym plikiem importu. "
                )
        raise NotImplementedError


class ImportPracownikowRow(models.Model):
    parent = models.ForeignKey(
        ImportPracownikow, on_delete=models.CASCADE, related_name="row_set"
    )

    wiersz_xls = models.PositiveSmallIntegerField()

    dane_z_xls = JSONField(null=True, blank=True)

    autor = models.ForeignKey(Autor, on_delete=models.CASCADE)
    jednostka = models.ForeignKey(Jednostka, on_delete=models.CASCADE)
    autor_jednostka = models.ForeignKey(Autor_Jednostka, on_delete=models.CASCADE)

    integracja_mozliwa = models.NullBooleanField()


# Numer	Nazwisko	Imię	ORCID	Tytuł/Stopień	Stanowisko	Grupa pracownicza	Nazwa jednostki
# Wydział	Data zatrudnienia	Data końca zatrudnienia 	"Podstawowe miejsce pracy
# TAK/NIE"	PBN UUID	BPP ID	Wymiar etatu
# 9530    Kowalski        Jan             lek. med.       Asystent
# Badawczo-dydaktyczna    Katedra i Klinika Dermatologii, Wenerologii i
# Dermatologii Dziecięcej   Wydział Lekarski        2016-10-01
# TAK             50      Pełny etat
