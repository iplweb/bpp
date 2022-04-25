from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import (
    ButtonHolder,
    Column,
    Fieldset,
    Layout,
    Row,
    Submit,
)
from dal import autocomplete
from django import forms
from django.core.exceptions import ValidationError
from django.forms import RadioSelect

from . import const
from .models.uczelnia import RaportSlotowUczelnia

from bpp.const import PBN_MAX_ROK, PBN_MIN_ROK
from bpp.models import Autor, Uczelnia
from bpp.util import formdefaults_html_after, formdefaults_html_before, year_last_month

OUTPUT_FORMATS = [
    ("html", "wyświetl w przeglądarce"),
    ("xlsx", "Microsoft Excel (XLSX)"),
]

OUTPUT_FORMATS_WITH_PDF = OUTPUT_FORMATS + [
    ("pdf", "Portable Document Format (PDF)"),
]


class AutorRaportSlotowForm(forms.Form):
    obiekt = forms.ModelChoiceField(
        label="Autor",
        queryset=Autor.objects.all(),
        widget=autocomplete.ModelSelect2(url="bpp:public-autor-autocomplete"),
    )

    od_roku = forms.IntegerField(initial=year_last_month, min_value=2016)
    do_roku = forms.IntegerField(initial=Uczelnia.objects.do_roku_default)

    minimalny_pk = forms.IntegerField(label="Minimalna wartość PK pracy", initial=0)

    dzialanie = forms.ChoiceField(
        label="Wygeneruj",
        choices=(
            (
                const.DZIALANIE_WSZYSTKO,
                "prace autora z punktacją dla dyscyplin za dany okres",
            ),
            (const.DZIALANIE_SLOT, "zbierz najlepsze prace do zadanej wielkości slotu"),
        ),
        initial="wszystko",
        widget=forms.RadioSelect,
    )

    slot = forms.DecimalField(
        label="Zadana wielkość slotu",
        required=False,
        max_digits=8,
        decimal_places=4,
        max_value=20,
    )

    _export = forms.ChoiceField(
        label="Format wyjściowy", choices=OUTPUT_FORMATS_WITH_PDF, required=True
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

        if (
            self.cleaned_data["dzialanie"] == const.DZIALANIE_WSZYSTKO
            and "slot" in self.cleaned_data
            and self.cleaned_data["slot"] is not None
        ):
            raise ValidationError(
                {
                    "slot": ValidationError(
                        "Gdy chcesz wygenerować wszystkie prace tego autora, pozostaw pole 'Slot' puste. ",
                        code="nie_podawaj_gdy_wszystko",
                    )
                }
            )

        if self.cleaned_data["dzialanie"] == const.DZIALANIE_SLOT and (
            "slot" not in self.cleaned_data
            or ("slot" in self.cleaned_data and self.cleaned_data["slot"] is None)
            or (
                "slot" in self.cleaned_data
                and self.cleaned_data["slot"] is not None
                and self.cleaned_data["slot"] <= 0
            )
        ):
            raise ValidationError(
                {
                    "slot": ValidationError(
                        "Podaj wartość slota do którego chcesz zbierać prace. Wartość musi być większa od zera. ",
                        code="podawaj_gdy_slot",
                    )
                }
            )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_class = "custom"
        self.helper.form_action = "."
        self.helper.layout = Layout(
            Fieldset(
                "Wybierz parametry",
                formdefaults_html_before(self),
                Row(Column("obiekt", css_class="large-12 small-12")),
                Row(Column("dzialanie", css_class="large-12 small-12")),
                Row(Column("slot", css_class="large-12 small-12")),
                Row(
                    Column("od_roku", css_class="large-6 small-6"),
                    Column("do_roku", css_class="large-6 small-6"),
                ),
                Row(Column("minimalny_pk")),
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
