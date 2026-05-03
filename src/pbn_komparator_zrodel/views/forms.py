"""Formularze filtrów dla widoków komparatora źródeł PBN."""

from django import forms

from .constants import DEFAULT_ROK_DO, DEFAULT_ROK_OD


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
    search = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Szukaj w nazwie/ISSN..."}),
    )
    dyscyplina = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Kod dyscypliny..."}),
    )
    tylko_rozbieznosci = forms.BooleanField(required=False, initial=True)
    bez_publikacji = forms.BooleanField(required=False, initial=False)
    bez_publikacji_2022_2025 = forms.BooleanField(required=False, initial=True)

    def clean_rok_od(self):
        return self.cleaned_data.get("rok_od") or DEFAULT_ROK_OD

    def clean_rok_do(self):
        return self.cleaned_data.get("rok_do") or DEFAULT_ROK_DO

    def clean_search(self):
        return self.cleaned_data.get("search") or ""

    def clean_dyscyplina(self):
        return self.cleaned_data.get("dyscyplina") or ""


class DyscyplinyFilterForm(forms.Form):
    """Formularz filtrów dla widoku dyscyplin."""

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
    search = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Szukaj w nazwie/ISSN..."}),
    )
    tylko_rozbieznosci = forms.BooleanField(required=False, initial=True)
    bez_publikacji = forms.BooleanField(required=False, initial=False)
    bez_publikacji_2022_2025 = forms.BooleanField(required=False, initial=True)
    wyswietlaj_nazwy = forms.BooleanField(required=False, initial=False)

    def clean_rok_od(self):
        return self.cleaned_data.get("rok_od") or DEFAULT_ROK_OD

    def clean_rok_do(self):
        return self.cleaned_data.get("rok_do") or DEFAULT_ROK_DO

    def clean_search(self):
        return self.cleaned_data.get("search") or ""
