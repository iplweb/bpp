from django import forms
from django.db import models
from django.db.models import JSONField

from import_common.core import matchuj_zrodlo
from import_common.models import ImportOperation, ImportRowMixin

from bpp.models import (
    IF_DECIMAL_PLACES,
    IF_MAX_DIGITS,
    ImpactFactorField,
    Punktacja_Zrodla,
    Zrodlo,
)


class ImportListRowValidationForm(forms.Form):
    full_journal_title = forms.CharField(max_length=512)
    journal_impact_factor = forms.DecimalField(
        max_digits=IF_MAX_DIGITS, decimal_places=IF_DECIMAL_PLACES
    )


class ImportListIf(ImportOperation):
    rok = models.PositiveSmallIntegerField()

    try_names = ["full_journal_title", "journal_impact_factor"]
    banned_names = []
    min_points = 2

    validation_form_class = ImportListRowValidationForm

    def import_single_row(self, xls_data, cleaned_data):
        zrodlo = matchuj_zrodlo(cleaned_data.get("full_journal_title"))
        impact_factor = cleaned_data.get("journal_impact_factor")

        res = ImportListIfRow(
            parent=self,
            dane_z_xls=xls_data,
            zrodlo=zrodlo,
            impact_factor=impact_factor,
        )

        if zrodlo is None:
            res.save()
            return

        try:
            pz = zrodlo.punktacja_zrodla_set.get(rok=self.rok)
        except Punktacja_Zrodla.DoesNotExist:
            pz = zrodlo.punktacja_zrodla_set.create(rok=self.rok)

        if pz.impact_factor != impact_factor:
            pz.impact_factor = impact_factor
            pz.save()

            res.zintegrowano = True

        res.save()

    def on_reset(self):
        self.get_details_set().delete()

    def get_details_set(self):
        return self.importlistifrow_set.all().select_related("zrodlo")


class ImportListIfRow(ImportRowMixin, models.Model):
    parent = models.ForeignKey(ImportListIf, on_delete=models.CASCADE)
    dane_z_xls = JSONField()

    zrodlo = models.ForeignKey(Zrodlo, null=True, blank=True, on_delete=models.SET_NULL)
    impact_factor = ImpactFactorField(null=True, blank=True)

    zintegrowano = models.BooleanField(default=False)
