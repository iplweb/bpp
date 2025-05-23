from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from crispy_forms_foundation.layout import ButtonHolder, Fieldset, Submit
from django import forms
from django.forms import RadioSelect

from ewaluacja2021.models import (
    ImportMaksymalnychSlotow,
    ZamowienieNaRaport,
    dyscypliny_naukowe_w_bazie,
)

from bpp.models import Dyscyplina_Naukowa


class ImportMaksymalnychSlotowForm(forms.ModelForm):
    class Meta:
        model = ImportMaksymalnychSlotow
        fields = ["plik"]

    def __init__(self, *args, **kw):
        self.helper = FormHelper()
        self.helper.form_class = "custom"
        self.helper.form_action = "."
        self.helper.layout = Layout(
            Fieldset(
                "Nowy import",
                "plik",
            ),
            ButtonHolder(
                Submit(
                    "submit",
                    "Dodaj",
                    css_id="id_submit",
                    css_class="submit button",
                ),
            ),
        )
        super().__init__(*args, **kw)


class ZamowienieNaRaportForm(forms.ModelForm):
    class Meta:
        model = ZamowienieNaRaport
        fields = ["dyscyplina_naukowa", "rodzaj"]
        widgets = {"dyscyplina_naukowa": RadioSelect, "rodzaj": RadioSelect}

    def __init__(self, *args, **kw):
        self.helper = FormHelper()
        self.helper.form_class = "custom"
        self.helper.form_action = "."
        self.helper.layout = Layout(
            Fieldset(
                "Nowy raport 3N",
                "dyscyplina_naukowa",
                "rodzaj",
            ),
            ButtonHolder(
                Submit(
                    "submit",
                    "Zamów",
                    css_id="id_submit",
                    css_class="submit button",
                ),
            ),
        )

        kw["initial"]["dyscyplina_naukowa"] = Dyscyplina_Naukowa.objects.filter(
            **dyscypliny_naukowe_w_bazie()
        ).first()

        super().__init__(*args, **kw)
