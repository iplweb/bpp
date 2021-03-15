from typing import Dict

from compat import DjangoJSONEncoder
from django.contrib.postgres.fields import JSONField
from django.db import models

from bpp.models import Dyscyplina_Naukowa, Zrodlo
from import_common.core import matchuj_dyscypline, matchuj_zrodlo
from import_common.exceptions import HeaderNotFoundException
from import_common.models import ImportOperation, ImportRowMixin
from import_common.util import XLSImportFile
from import_dyscyplin_zrodel import const


class ImportDyscyplinZrodel(ImportOperation):
    plik_xls = models.FileField()

    _ignore_headers = None
    _header_mapping = None

    redirect_prefix = "import_dyscyplin_zrodel:ImportDyscyplinZrodel"

    def on_reset(self):
        self.importdyscyplinzrodelrow_set.all().delete()

    def _map_key_names(self, elem: Dict[str, str]):
        """Cel tej procedury to usunąć kolumny XLS dla dyscyplin naukowych,
        których nie ma zdefiniowanych w systemie"""
        if self._ignore_headers or self._header_mapping:
            return

        self._ignore_headers = []
        self._header_mapping = {}

        column_names = elem.keys()
        found = False
        for fmt, wartosc in [(const.DASH, "101_0"), (const.NUMBER, "101")]:
            if wartosc in column_names:
                found = True
                break

        if not found:
            raise HeaderNotFoundException(
                "Nagłówek zapisany w formacie, na który to oprogramowanie nie zostało "
                "przygotowane. Upewnij się, że kody dyscyplin mają postać 3 cyfr (np. "
                "101) i że komórki z tymi wartościami są typu liczbowego"
            )

        if fmt == const.DASH:
            headers = const.KODY_DYSCYPLIN_XLS_DASH
        elif fmt == const.NUMBER:
            headers = const.KODY_DYSCYPLIN_XLS_NUMBER

        header_to_name = dict(zip(headers, const.NAZWY_DYSCYPLIN_XLS))

        for elem in column_names:
            if elem in headers:
                d = matchuj_dyscypline(kod=elem, nazwa=header_to_name.get(elem))
                if d is None:
                    self._ignore_headers.append(elem)
                    continue
                self._header_mapping[elem] = d

    def get_xls_import_file(self):
        return XLSImportFile(
            self.plik_xls.path,
            try_names=const.HEADER_NAMES,
            min_points=5,
            only_first_sheet=True,
        )

    def import_single_row(self, xls_data, cleaned_data=None):

        self._map_key_names(xls_data)

        z = matchuj_zrodlo(
            xls_data.get("tytuł_1"),
            issn=xls_data.get("issn"),
            e_issn=xls_data.get("e_issn"),
            alt_nazwa=xls_data.get("tytuł_2"),
        )

        row = self.importdyscyplinzrodelrow_set.create(
            zrodlo=z,
            dane_z_xls=xls_data,
        )

        created = False
        for kolumna, dyscyplina in self._header_mapping.items():
            if xls_data.get(kolumna, "").strip() != "":
                row.importdyscyplinzrodelrowdyscypliny_set.create(dyscyplina=dyscyplina)
                created = True

        if created and z is not None:
            z.dyscyplina_zrodla_set.all().delete()
            for elem in row.importdyscyplinzrodelrowdyscypliny_set.all():
                z.dyscyplina_zrodla_set.create(dyscyplina=elem.dyscyplina)

    def get_details_set(self):
        return (
            self.importdyscyplinzrodelrow_set.all()
            .select_related("zrodlo")
            .prefetch_related("importdyscyplinzrodelrowdyscypliny_set__dyscyplina")
        )


class ImportDyscyplinZrodelRow(ImportRowMixin, models.Model):
    parent = models.ForeignKey(ImportDyscyplinZrodel, on_delete=models.CASCADE)

    dane_z_xls = JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)

    zrodlo = models.ForeignKey(Zrodlo, on_delete=models.SET_NULL, null=True, blank=True)


class ImportDyscyplinZrodelRowDyscypliny(models.Model):
    parent = models.ForeignKey(ImportDyscyplinZrodelRow, on_delete=models.CASCADE)
    dyscyplina = models.ForeignKey(Dyscyplina_Naukowa, on_delete=models.CASCADE)
