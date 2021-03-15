from math import ceil

from django.db import models

from import_common.exceptions import XLSParseError
from import_common.util import XLSImportFile
from long_running.models import Operation
from long_running.notification_mixins import ASGINotificationMixin


class ImportOperation(ASGINotificationMixin, Operation):
    plik_xls = models.FileField()

    try_names = None
    banned_names = None
    min_points = None

    validation_form_class = None

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

    def perform(self):
        x = self.get_xls_import_file()

        total = x.count()
        five_percent = int(ceil(total / 50.0))
        form_class = self.get_validation_form_class()

        for no, elem in enumerate(x.data()):
            cleaned_data = None
            if form_class:
                form = form_class(elem)
                if not form.is_valid():
                    if self.ignore_bad_rows:
                        continue
                    raise XLSParseError(elem, form, "wstępna weryfikacja danych")

                cleaned_data = form.cleaned_data

            self.import_single_row(xls_data=elem, cleaned_data=cleaned_data)

            if no % five_percent == 0:
                self.send_progress(no * 100.0 / total)

    class Meta:
        abstract = True


class ImportRowMixin:
    def nr_arkusza(self):
        return self.dane_z_xls.get("__xls_loc_sheet__")

    def nr_wiersza(self):
        return self.dane_z_xls.get("__xls_loc_row__")
