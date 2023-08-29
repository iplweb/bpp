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
from django.core.exceptions import ValidationError
from django.forms import RadioSelect

from . import OUTPUT_FORMATS

from bpp.const import PBN_MAX_ROK, PBN_MIN_ROK
from bpp.models import Uczelnia
from bpp.util import formdefaults_html_after, formdefaults_html_before


class ParametryRaportSlotowEwaluacjaForm(forms.Form):
    od_roku = forms.IntegerField(
        initial=Uczelnia.objects.do_roku_default, min_value=PBN_MIN_ROK
    )
    do_roku = forms.IntegerField(
        initial=Uczelnia.objects.do_roku_default,
        min_value=PBN_MIN_ROK,
        max_value=PBN_MAX_ROK,
    )

    _export = forms.ChoiceField(
        label="Format wyjściowy",
        choices=OUTPUT_FORMATS,
        required=True,
        widget=RadioSelect,
        initial="html",
    )
    upowaznienie_pbn = forms.NullBooleanField(
        required=False,
        # widget=RadioSelect,
    )

    def clean(self):
        if "od_roku" in self.cleaned_data and "do_roku" in self.cleaned_data:
            if self.cleaned_data["od_roku"] > self.cleaned_data["do_roku"]:
                raise ValidationError(
                    {
                        "od_roku": ValidationError(
                            'Pole musi być większe lub równe jak pole "Do roku".',
                            code="od_do_zle",
                        )
                    }
                )

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
                Row(Column("upowaznienie_pbn", css_class="large-12 small-12")),
                Row(Column("_export")),
                formdefaults_html_after(self),
            ),
            ButtonHolder(
                Submit(
                    "submit",
                    "Pobierz raport",
                    css_id="id_submit",
                    css_class="submit button",
                ),
            ),
        )

        super().__init__(*args, **kwargs)
