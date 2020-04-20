# -*- encoding: utf-8 -*-
from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import Layout, Fieldset, Submit, Column, Row
from django import forms

from eksport_pbn.models import PlikEksportuPBN

from django.utils.timezone import now


def zakres_lat():
    z = list(reversed(range(2013, now().date().year + 1)))
    for elem in zip(z, map(str, z)):
        yield elem


class EksportDoPBNForm(forms.ModelForm):
    od_roku = forms.ChoiceField(choices=zakres_lat)
    do_roku = forms.ChoiceField(choices=zakres_lat)

    class Meta:
        model = PlikEksportuPBN
        fields = [
            "od_roku",
            "do_roku",
            "artykuly",
            "ksiazki",
            "rozdzialy",
            "rodzaj_daty",
            "od_daty",
            "do_daty",
        ]

    def __init__(self, *args, **kw):
        super(EksportDoPBNForm, self).__init__(*args, **kw)

        helper = FormHelper(self)
        helper.form_class = "custom"
        helper.layout = Layout(
            Fieldset(
                "Zamów eksport PBN",
                Row(
                    Column("od_roku", css_class="small-6 large-6"),
                    Column("do_roku", css_class="small-6 large-6"),
                ),
                Row(
                    Column("artykuly", css_class="small-4 large-4"),
                    Column("ksiazki", css_class="small-4 large-4"),
                    Column("rozdzialy", css_class="small-4 large-4"),
                ),
                "rodzaj_daty",
                Row(
                    Column("od_daty", css_class="small-6 large-6"),
                    Column("do_daty", css_class="small-6 large-6"),
                ),
                Submit(
                    "submit", "Zamów", css_id="id_submit", css_class="button submit"
                ),
            )
        )
        self.helper = helper

    def clean(self):
        cleaned_data = super(EksportDoPBNForm, self).clean()

        od_roku = cleaned_data.get("od_roku")
        do_roku = cleaned_data.get("do_roku")

        if od_roku is not None and do_roku is not None:
            if od_roku > do_roku:
                self.errors["od_roku"] = ["Skoryguj wartość."]
                self.errors["do_roku"] = ["Skoryguj wartość."]
                raise forms.ValidationError(
                    "Wartość w polu 'Od roku' musi być niższa lub równa, niż w polu 'Do roku'."
                )

        od_daty = cleaned_data.get("od_daty")
        do_daty = cleaned_data.get("do_daty")

        if od_daty is not None and do_daty is not None:
            if od_daty > do_daty:
                self.errors["od_daty"] = ["Skoryguj wartość."]
                self.errors["do_daty"] = ["Skoryguj wartość."]
                raise forms.ValidationError(
                    "Wartość w polu 'Od daty' musi być wcześniejsza lub równa, niż w polu 'Do daty'."
                )

        if (
            not cleaned_data.get("artykuly")
            and not cleaned_data.get("ksiazki")
            and not cleaned_data.get("rozdzialy")
        ):
            self.errors["artykuly"] = ["Kliknij tu..."]
            self.errors["ksiazki"] = ["albo tu..."]
            self.errors["rozdzialy"] = ["... a przynajmniej tu."]
            raise forms.ValidationError(
                "Wybierz przynajmniej jedną opcję: artykuły, książki lub rozdziały."
            )
