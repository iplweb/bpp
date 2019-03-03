# -*- encoding: utf-8 -*-


from django.core.exceptions import MultipleObjectsReturned
from django.db import models
from django.db import transaction
from django.db.models import Transform, CASCADE, SET_NULL

from bpp import fields
from bpp.models.zrodlo import Zrodlo, Punktacja_Zrodla
from integrator2.models.base import BaseIntegrationElement
from integrator2.util import read_xls_data
from .base import BaseIntegration


class UpperCase(Transform):
    lookup_name = 'upper'
    # bilateral = True # <- chyba w 1.8?
    # function = 'UPPER' <- j/w

    def as_sql(self, qn, connection):
        return "upper(" + self.lhs.as_sql(qn, connection)[0] + ")", []

from django.db.models import CharField, TextField

CharField.register_lookup(UpperCase)
TextField.register_lookup(UpperCase)


class ListaMinisterialnaElement(BaseIntegrationElement):
    parent = models.ForeignKey("ListaMinisterialnaIntegration", CASCADE)

    nazwa = models.TextField()
    issn = models.CharField("ISSN", max_length=32, blank=True, null=True)
    e_issn = models.CharField("e-ISSN", max_length=32, blank=True, null=True)
    punkty_kbn = models.IntegerField()
    zrodlo = models.ForeignKey(Zrodlo, SET_NULL, blank=True, null=True)

    class Meta:
        ordering = ['nazwa',]

    def __iter__(self):
        """Zwraca kolejne elementy do wyświetlenia na stronie w widoku tabeli.

        Kolejność zwracanych pól powinna odpowiadać kolejności pól nagłówka zwracanych przez
        ListaMinisterialnaIntegration.header_columns
        """
        return iter([self.nazwa, self.issn, self.e_issn, self.punkty_kbn])

def last_year():
    from datetime import datetime
    return datetime.now().date().year - 1


class ListaMinisterialnaIntegration(BaseIntegration):
    """Importuje wartości punktów KBN dla czasopism z list ministerialnych A, B, C.
    Wartości wejściowe w plikach to nazwa czasopisma, ISSN i opcjonalnie e-ISSN.
    """

    year = fields.YearField("Rok", default=last_year, help_text="Rok dla którego została wydana ta lista ministerialna")

    klass = ListaMinisterialnaElement

    class Meta:
        verbose_name = "integracja list ministerialnych"
        ordering = ['-uploaded_on']

    def input_file_to_dict_stream(self, limit=None, limit_sheets=None):
        gen = read_xls_data(
                self.file.path,
                {
                    "TYTUŁ CZASOPISMA": "nazwa",
                    "NR ISSN": "issn",
                    "NR E-ISSN": "e_issn",
                    "LICZBA PUNKTÓW ZA PUBLIKACJĘ W CZASOPIŚMIE NAUKOWYM ": "punkty_kbn"
                },
                "Lp.",
                limit=limit, limit_sheets=limit_sheets)
        next(gen)  # wiersz z cyferkami
        return gen

    def header_columns(self):
        return ["Nazwa", "ISSN", "E-ISSN", "Punkty"]

    def dict_stream_to_db(self, dict_stream=None, limit=None):
        if dict_stream is None:
            # Tylko z pierwszego sheet
            dict_stream = self.input_file_to_dict_stream(limit=limit, limit_sheets=1)

        for elem in dict_stream:
            ListaMinisterialnaElement.objects.create(
                    parent=self,
                    **dict([(str(x), y) for x, y in list(elem.items()) if x is not None and x != "__sheet__"]))
        pass

    strategie = [lambda obj: Zrodlo.objects.get(issn=obj.issn) if obj.issn is not None else None,
                 lambda obj: Zrodlo.objects.get(e_issn=obj.e_issn) if obj.e_issn is not None else None,
                 lambda obj: Zrodlo.objects.get(nazwa__upper=obj.nazwa.upper()) if obj.nazwa is not None else None]

    @transaction.atomic
    def match_single_record(self, elem):
        z = None
        for no, strategia in enumerate(self.strategie):
            try:
                z = strategia(elem)
                if z is not None:
                    break
            except MultipleObjectsReturned:
                elem.extra_info = "strategia %i zwraca > 1 obiekt" % no
                break
            except Zrodlo.DoesNotExist:
                continue
        if z:
            elem.zrodlo = z
            elem.moze_byc_zintegrowany_automatycznie = True
        else:
            elem.extra_info = "Brak takiego źródła w bazie danych"

    @transaction.atomic
    def integrate_single_record(self, elem):
        rok = elem.parent.year
        pz = Punktacja_Zrodla.objects.get_or_create(zrodlo=elem.zrodlo, rok=rok)[0]
        pz.punkty_kbn = elem.punkty_kbn
        pz.save()
