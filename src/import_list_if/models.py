from django import forms
from django.db import models, transaction
from django.db.models import JSONField
from liveops.models import LiveOperation

from bpp.models import (
    IF_DECIMAL_PLACES,
    IF_MAX_DIGITS,
    ImpactFactorField,
    Punktacja_Zrodla,
    Zrodlo,
)
from import_common.core import matchuj_zrodlo
from import_common.exceptions import XLSParseError
from import_common.models import ImportRowMixin
from import_common.util import XLSImportFile


class ImportListRowValidationForm(forms.Form):
    full_journal_title = forms.CharField(max_length=512)
    journal_impact_factor = forms.DecimalField(
        max_digits=IF_MAX_DIGITS, decimal_places=IF_DECIMAL_PLACES
    )


class ImportListIf(LiveOperation):
    rok = models.PositiveSmallIntegerField()
    plik_xls = models.FileField(upload_to="protected/import_common/")

    try_names = ["full_journal_title", "journal_impact_factor"]
    banned_names = []
    min_points = 2

    validation_form_class = ImportListRowValidationForm
    ignore_bad_rows = False

    def get_validation_form_class(self):
        return self.validation_form_class

    def get_xls_import_file(self):
        return XLSImportFile(
            self.plik_xls.path,
            try_names=self.try_names,
            banned_names=self.banned_names,
            min_points=self.min_points,
        )

    def run(self, p):
        # Punkt wejścia liveops (dawniej ImportOperation.perform()). Owijamy
        # ciało w transaction.atomic() dla parytetu z legacy task_perform:
        # OperationCancelled / XLSParseError cofa (rollback) już zapisane
        # wiersze → import jest all-or-nothing. p.result() jest POZA blokiem
        # (i tak defer push przez transaction.on_commit).
        with transaction.atomic():
            x = self.get_xls_import_file()
            total = x.count()
            form_class = self.get_validation_form_class()

            for no, elem in enumerate(x.data()):
                p.check_cancelled()

                cleaned_data = None
                if form_class:
                    form = form_class(elem)
                    if not form.is_valid():
                        if self.ignore_bad_rows:
                            continue
                        raise XLSParseError(elem, form, "wstępna weryfikacja danych")
                    cleaned_data = form.cleaned_data

                self.import_single_row(xls_data=elem, cleaned_data=cleaned_data)

                if total:
                    p.percent(int((no + 1) * 100 / total))

        wiersze = self.get_details_set()
        p.result(
            {
                "total": total,
                "zintegrowano": wiersze.filter(zintegrowano=True).count(),
                "niedopasowane": wiersze.filter(zrodlo__isnull=True).count(),
                "rok": self.rok,
            }
        )

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

    def on_restart(self):
        # Hook liveops (RestartView) — odpowiednik dawnego on_reset(). Kasuje
        # wiersze poprzedniego przebiegu, by restart zaczynał od czysta.
        self.get_details_set().delete()

    def get_details_set(self):
        return self.importlistifrow_set.all().select_related("zrodlo")


class ImportListIfRow(ImportRowMixin, models.Model):
    parent = models.ForeignKey(ImportListIf, on_delete=models.CASCADE)
    dane_z_xls = JSONField()

    zrodlo = models.ForeignKey(Zrodlo, null=True, blank=True, on_delete=models.SET_NULL)
    impact_factor = ImpactFactorField(null=True, blank=True)

    zintegrowano = models.BooleanField(default=False)
