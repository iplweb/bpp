import os

from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Submit
from crispy_forms_foundation.layout import Column, Fieldset, Layout, Row
from django import forms
from django.core.exceptions import ValidationError

from bpp.util import formdefaults_html_after, formdefaults_html_before
from import_punktacji_zrodel.models import ImportPunktacjiZrodel


class NowyImportForm(forms.ModelForm):
    class Meta:
        model = ImportPunktacjiZrodel
        fields = [
            "plik",
            "rok",
            "importuj_impact_factor",
            "importuj_kwartyl_wos",
            "ignoruj_zrodla_bez_odpowiednika",
            "nie_porownuj_po_tytulach",
            "zapisz_zmiany_do_bazy",
        ]

    def clean_plik(self):
        plik = self.cleaned_data.get("plik")
        if plik:
            ext = os.path.splitext(plik.name)[1].lower()
            if ext not in (".xlsx", ".xls", ".csv"):
                raise ValidationError(
                    "Niewłaściwy format pliku. Dozwolone: .xlsx, .xls, .csv "
                    f"(otrzymano: {ext})."
                )
        return plik

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_class = "custom"
        self.helper.form_action = "."
        self.helper.layout = Layout(
            Fieldset(
                "Wybierz parametry importu",
                formdefaults_html_before(self),
                Row(Column("rok", css_class="large-12 small-12")),
                Row(
                    Column(
                        "importuj_impact_factor",
                        css_class="large-12 small-12",
                    )
                ),
                Row(Column("importuj_kwartyl_wos", css_class="large-12 small-12")),
                Row(
                    Column(
                        "ignoruj_zrodla_bez_odpowiednika",
                        css_class="large-12 small-12",
                    )
                ),
                Row(
                    Column(
                        "nie_porownuj_po_tytulach",
                        css_class="large-12 small-12",
                    )
                ),
                Row(
                    Column(
                        "zapisz_zmiany_do_bazy",
                        css_class="large-12 small-12",
                    )
                ),
                Row(Column("plik", css_class="large-12 small-12")),
                formdefaults_html_after(self),
            ),
            ButtonHolder(
                Submit(
                    "submit",
                    "Wczytaj i pokaż podgląd",
                    css_id="id_submit",
                    css_class="submit button",
                ),
            ),
        )
        super().__init__(*args, **kwargs)
