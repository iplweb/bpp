import os

from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Submit
from crispy_forms_foundation.layout import Column, Fieldset, Layout, Row
from django import forms
from django.core.exceptions import ValidationError

from bpp.util import formdefaults_html_after, formdefaults_html_before
from import_list_ministerialnych.models import ImportListMinisterialnych


class NowyImportForm(forms.ModelForm):
    class Meta:
        model = ImportListMinisterialnych
        fields = [
            "plik",
            "rok",
            "zapisz_zmiany_do_bazy",
            "importuj_dyscypliny",
            "importuj_punktacje",
            "ignoruj_zrodla_bez_odpowiednika",
            "nie_porownuj_po_tytulach",
        ]

    def clean_plik(self):
        plik = self.cleaned_data.get("plik")
        if plik:
            # Check file extension
            file_extension = os.path.splitext(plik.name)[1].lower()
            valid_extensions = [".xlsx", ".xls"]

            if file_extension not in valid_extensions:
                raise ValidationError(
                    f"Niewłaściwy format pliku. Proszę przesłać plik Excel (.xlsx lub .xls). "
                    f"Otrzymano plik z rozszerzeniem: {file_extension}"
                )

            # Check MIME type if available
            if hasattr(plik, "content_type"):
                valid_mime_types = [
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
                    "application/vnd.ms-excel",  # xls
                    "application/octet-stream",  # sometimes Excel files are detected as this
                ]
                if plik.content_type not in valid_mime_types:
                    # Don't reject based on MIME type alone, just warn
                    # Some browsers may report incorrect MIME types
                    if file_extension not in valid_extensions:
                        raise ValidationError(
                            "Niewłaściwy typ pliku. Proszę przesłać plik Excel (.xlsx lub .xls)."
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
                    Column("importuj_dyscypliny", css_class="large-12 small-12"),
                ),
                Row(
                    Column("importuj_punktacje", css_class="large-12 small-12"),
                ),
                Row(
                    Column(
                        "ignoruj_zrodla_bez_odpowiednika", css_class="large-12 small-12"
                    ),
                ),
                Row(
                    Column("nie_porownuj_po_tytulach", css_class="large-12 small-12"),
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
                    "Przeprowadź import",
                    css_id="id_submit",
                    css_class="submit button",
                ),
            ),
        )

        super().__init__(*args, **kwargs)
