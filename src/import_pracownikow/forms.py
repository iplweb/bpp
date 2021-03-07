from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Submit
from crispy_forms_foundation.layout import Column, Fieldset, Layout, Row
from django import forms

from bpp.util import formdefaults_html_after, formdefaults_html_before
from import_pracownikow.models import ImportPracownikow


class NowyImportForm(forms.ModelForm):
    class Meta:
        model = ImportPracownikow
        fields = ["plik_xls"]

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_class = "custom"
        self.helper.form_action = "."
        self.helper.layout = Layout(
            Fieldset(
                "Wybierz parametry",
                formdefaults_html_before(self),
                Row(
                    Column("plik_xls", css_class="large-12 small-12"),
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

        super(NowyImportForm, self).__init__(*args, **kwargs)
