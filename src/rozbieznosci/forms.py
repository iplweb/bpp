from datetime import datetime

from django import forms

from bpp.models import Charakter_Formalny
from rozbieznosci.core import (
    DEFAULT_TRYB_ZRODLA,
    TRYB_ROWNIEZ_ZEROWE,
    TRYB_STANDARD,
    TRYB_WYLACZNIE_ZEROWE,
    TRYBY_ZRODLA,
)

DEFAULT_ROK_OD = 2022
CURRENT_YEAR = datetime.now().year
OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE = 20

TRYB_ZRODLA_CHOICES = [
    (TRYB_STANDARD, "Standardowy"),
    (TRYB_ROWNIEZ_ZEROWE, "Pokazuj również zerowe rekordy"),
    (TRYB_WYLACZNIE_ZEROWE, "Pokazuj wyłącznie zerowe rekordy"),
]


class SetForm(forms.Form):
    _set = forms.IntegerField(min_value=0)


class IgnoreForm(forms.Form):
    _ignore = forms.IntegerField(min_value=0)


class FilterForm(forms.Form):
    rok_od = forms.IntegerField(
        min_value=1900,
        max_value=2100,
        required=False,
        widget=forms.NumberInput(
            attrs={"class": "input-group-field", "style": "width: 80px"}
        ),
    )
    rok_do = forms.IntegerField(
        min_value=1900,
        max_value=2100,
        required=False,
        widget=forms.NumberInput(
            attrs={"class": "input-group-field", "style": "width: 80px"}
        ),
    )
    tytul = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Szukaj w tytule..."}),
    )
    tryb_zrodla = forms.ChoiceField(choices=TRYB_ZRODLA_CHOICES, required=False)
    kasuj_przy_pustym_zrodle = forms.BooleanField(required=False)
    charaktery_formalne = forms.ModelMultipleChoiceField(
        queryset=Charakter_Formalny.objects.all(), required=False
    )

    def clean_rok_od(self):
        return self.cleaned_data.get("rok_od") or DEFAULT_ROK_OD

    def clean_rok_do(self):
        return self.cleaned_data.get("rok_do") or CURRENT_YEAR

    def clean_tytul(self):
        return self.cleaned_data.get("tytul") or ""

    def clean_tryb_zrodla(self):
        tryb = self.cleaned_data.get("tryb_zrodla")
        return tryb if tryb in TRYBY_ZRODLA else DEFAULT_TRYB_ZRODLA
