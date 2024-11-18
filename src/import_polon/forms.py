from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Submit
from crispy_forms_foundation.layout import Column, Fieldset, Layout, Row
from django import forms

from import_polon.models import ImportPlikuPolon

from bpp.util import formdefaults_html_after, formdefaults_html_before


class NowyImportForm(forms.ModelForm):
    class Meta:
        model = ImportPlikuPolon
        fields = [
            "plik",
            "rok",
            "zapisz_zmiany_do_bazy",
            "ukryj_niezmatchowanych_autorow",
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
