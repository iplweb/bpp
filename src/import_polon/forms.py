import os

from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Submit
from crispy_forms_foundation.layout import Column, Fieldset, Layout, Row
from django import forms
from django.core.exceptions import ValidationError

from import_polon.models import ImportPlikuAbsencji, ImportPlikuPolon

from bpp.util import formdefaults_html_after, formdefaults_html_before


class NowyImportAbsencjiForm(forms.ModelForm):
    class Meta:
        model = ImportPlikuAbsencji
        fields = ["plik", "zapisz_zmiany_do_bazy"]

    def clean_plik(self):
        plik = self.cleaned_data.get("plik")
        if plik:
            # Check file extension
            file_extension = os.path.splitext(plik.name)[1].lower()
            valid_extensions = [".xlsx", ".xls", ".csv"]

            if file_extension not in valid_extensions:
                raise ValidationError(
                    f"Niewłaściwy format pliku. Proszę przesłać plik Excel (.xlsx, .xls) lub CSV (.csv). "
                    f"Otrzymano plik z rozszerzeniem: {file_extension}"
                )

            # Check MIME type if available
            if hasattr(plik, "content_type"):
                valid_mime_types = [
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
                    "application/vnd.ms-excel",  # xls
                    "text/csv",  # csv
                    "application/csv",  # csv alternative
                    "application/octet-stream",  # sometimes files are detected as this
                ]
                if plik.content_type not in valid_mime_types:
                    # Don't reject based on MIME type alone if extension is valid
                    # Some browsers may report incorrect MIME types
                    if file_extension not in valid_extensions:
                        raise ValidationError(
                            "Niewłaściwy typ pliku. Proszę przesłać plik Excel (.xlsx, .xls) lub CSV (.csv)."
                        )

        return plik

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_class = "custom"
        self.helper.form_action = "."
        self.helper.layout = Layout(
            Fieldset(
                "Wybierz parametry",
                formdefaults_html_before(self),
                Row(
                    Column("plik", css_class="large-12 small-12"),
                ),
                Row(
                    Column("zapisz_zmiany_do_bazy", css_class="large-12 small-12"),
                ),
                formdefaults_html_after(self),
            ),
            ButtonHolder(
                Submit(
                    "submit",
                    "Utwórz import",
                    css_id="id_submit",
                    css_class="submit button",
                ),
            ),
        )

        super().__init__(*args, **kwargs)


class NowyImportForm(forms.ModelForm):
    class Meta:
        model = ImportPlikuPolon
        fields = [
            "plik",
            "rok",
            "zapisz_zmiany_do_bazy",
            "ukryj_niezmatchowanych_autorow",
        ]

    def clean_plik(self):
        plik = self.cleaned_data.get("plik")
        if plik:
            # Check file extension
            file_extension = os.path.splitext(plik.name)[1].lower()
            valid_extensions = [".xlsx", ".xls", ".csv"]

            if file_extension not in valid_extensions:
                raise ValidationError(
                    f"Niewłaściwy format pliku. Proszę przesłać plik Excel (.xlsx, .xls) lub CSV (.csv). "
                    f"Otrzymano plik z rozszerzeniem: {file_extension}"
                )

            # Check MIME type if available
            if hasattr(plik, "content_type"):
                valid_mime_types = [
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
                    "application/vnd.ms-excel",  # xls
                    "text/csv",  # csv
                    "application/csv",  # csv alternative
                    "application/octet-stream",  # sometimes files are detected as this
                ]
                if plik.content_type not in valid_mime_types:
                    # Don't reject based on MIME type alone if extension is valid
                    # Some browsers may report incorrect MIME types
                    if file_extension not in valid_extensions:
                        raise ValidationError(
                            "Niewłaściwy typ pliku. Proszę przesłać plik Excel (.xlsx, .xls) lub CSV (.csv)."
                        )

        return plik

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_class = "custom"
        self.helper.form_action = "."
        self.helper.layout = Layout(
            Fieldset(
                "Wybierz parametry",
                formdefaults_html_before(self),
                Row(
                    Column("rok", css_class="large-12 small-12"),
                ),
                Row(
                    Column(
                        "ukryj_niezmatchowanych_autorow", css_class="large-12 small-12"
                    ),
                ),
                Row(
                    Column("zapisz_zmiany_do_bazy", css_class="large-12 small-12"),
                ),
                Row(
                    Column("plik", css_class="large-12 small-12"),
                ),
                formdefaults_html_after(self),
            ),
            ButtonHolder(
                Submit(
                    "submit",
                    "Utwórz import",
                    css_id="id_submit",
                    css_class="submit button",
                ),
            ),
        )

        super().__init__(*args, **kwargs)
