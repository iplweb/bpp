from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from long_running.models import Operation
from long_running.notification_mixins import ASGINotificationMixin

from bpp.fields import YearField
from bpp.models import Autor, Dyscyplina_Naukowa


class ImportPlikuAbsencji(ASGINotificationMixin, Operation):
    plik = models.FileField(upload_to="import_polon")
    zapisz_zmiany_do_bazy = models.BooleanField(default=False)

    def on_reset(self):
        self.wierszimportuplikuabsencji_set.all().delete()

    def perform(self):
        from .core.import_absencji import analyze_file_import_absencji

        analyze_file_import_absencji(self.plik.path, self)

    def get_details_set(self):
        return self.wierszimportuplikuabsencji_set.all()


class WierszImportuPlikuAbsencji(models.Model):
    parent = models.ForeignKey(ImportPlikuAbsencji, on_delete=models.CASCADE)
    dane_z_xls = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    nr_wiersza = models.PositiveSmallIntegerField()

    autor = models.ForeignKey(Autor, on_delete=models.SET_NULL, null=True, blank=True)
    rok = models.PositiveSmallIntegerField(null=True, blank=True)
    ile_dni = models.PositiveSmallIntegerField(null=True, blank=True)

    wymaga_zmiany = models.BooleanField(default=None, null=True, blank=True)
    rezultat = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ("nr_wiersza",)


class ImportPlikuPolon(ASGINotificationMixin, Operation):
    rok = YearField()
    plik = models.FileField(upload_to="import_polon")
    ukryj_niezmatchowanych_autorow = models.BooleanField(default=True)
    zapisz_zmiany_do_bazy = models.BooleanField(default=False)

    def on_reset(self):
        self.wierszimportuplikupolon_set.all().delete()

    def perform(self):
        from import_polon.core import analyze_file_import_polon

        analyze_file_import_polon(self.plik.path, self)

    def get_details_set(self):
        return WierszImportuPlikuPolon.objects.filter(parent=self)


class WierszImportuPlikuPolon(models.Model):
    parent = models.ForeignKey(ImportPlikuPolon, on_delete=models.CASCADE)
    dane_z_xls = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    nr_wiersza = models.PositiveSmallIntegerField()

    autor = models.ForeignKey(Autor, on_delete=models.SET_NULL, null=True, blank=True)
    dyscyplina_naukowa = models.ForeignKey(
        Dyscyplina_Naukowa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    subdyscyplina_naukowa = models.ForeignKey(
        Dyscyplina_Naukowa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    rezultat = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ("nr_wiersza",)
