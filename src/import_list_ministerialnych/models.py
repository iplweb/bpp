from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from long_running.models import Operation
from long_running.notification_mixins import ASGINotificationMixin

from bpp.fields import YearField
from bpp.models import Zrodlo


class ImportListMinisterialnych(ASGINotificationMixin, Operation):
    rok = YearField()
    plik = models.FileField(upload_to="import_list_ministerialnych")
    zapisz_zmiany_do_bazy = models.BooleanField(default=False)
    importuj_dyscypliny = models.BooleanField(default=True)
    importuj_punktacje = models.BooleanField(default=True)
    ignoruj_zrodla_bez_odpowiednika = models.BooleanField(default=True)

    def on_reset(self):
        self.wierszimportulistyministerialnej_set.all().delete()

    def perform(self):
        from import_list_ministerialnych.core import (
            analyze_excel_file_import_list_ministerialnych,
        )

        analyze_excel_file_import_list_ministerialnych(self.plik.path, self)

    def get_details_set(self):
        return WierszImportuListyMinisterialnej.objects.filter(parent=self)


class WierszImportuListyMinisterialnej(models.Model):
    parent = models.ForeignKey(ImportListMinisterialnych, on_delete=models.CASCADE)
    dane_z_xls = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    nr_wiersza = models.PositiveIntegerField()

    zrodlo = models.ForeignKey(Zrodlo, on_delete=models.SET_NULL, null=True, blank=True)

    rezultat = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ("nr_wiersza",)
