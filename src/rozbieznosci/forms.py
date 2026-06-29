from datetime import datetime

from django import forms

DEFAULT_ROK_OD = 2022
CURRENT_YEAR = datetime.now().year
OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE = 20


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
    pokaz_puste_zrodla = forms.BooleanField(required=False)

    def clean_rok_od(self):
        return self.cleaned_data.get("rok_od") or DEFAULT_ROK_OD

    def clean_rok_do(self):
        return self.cleaned_data.get("rok_do") or CURRENT_YEAR

    def clean_tytul(self):
        return self.cleaned_data.get("tytul") or ""
