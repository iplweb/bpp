from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import (
    ButtonHolder,
    Column,
    Fieldset,
    Layout,
    Row,
    Submit,
)
from django import forms

from ..models.uczelnia import RaportSlotowUczelnia

from bpp.util import formdefaults_html_after, formdefaults_html_before


class UtworzRaportSlotowUczelniaForm(forms.ModelForm):
    class Meta:
        model = RaportSlotowUczelnia
        fields = [
            "od_roku",
            "do_roku",
            "akcja",
            "slot",
            "minimalny_pk",
            "dziel_na_jednostki_i_wydzialy",
            "pokazuj_zerowych",
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
                    Column("od_roku", css_class="large-6 small-6"),
                    Column("do_roku", css_class="large-6 small-6"),
                ),
                Row(Column("akcja", css_class="large-12 small-12")),
                Row(Column("slot", css_class="large-12 small-12")),
                Row(Column("minimalny_pk", css_class="large-12 small-12")),
                Row(Column("dziel_na_jednostki_i_wydzialy")),
                Row(Column("pokazuj_zerowych")),
                formdefaults_html_after(self),
            ),
            ButtonHolder(
                Submit(
                    "submit",
                    "Utwórz raport",
                    css_id="id_submit",
                    css_class="submit button",
                ),
            ),
        )

        super().__init__(*args, **kwargs)
