from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Submit
from crispy_forms_foundation.layout import Column, Fieldset, Layout, Row
from django import forms

from import_list_ministerialnych.models import ImportListMinisterialnych

from bpp.util import formdefaults_html_after, formdefaults_html_before


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
        ]

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
