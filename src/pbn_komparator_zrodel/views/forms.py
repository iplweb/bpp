"""Formularze filtrów dla widoków komparatora źródeł PBN."""

from django import forms

from .constants import DEFAULT_ROK_DO, DEFAULT_ROK_OD


class _LataOkresuMixin:
    """Puste „rok od/do” = lata okresu ewaluacji (``domyslne_lata``,
    zwykle okres wybrany na pasku okresu)."""

    def __init__(self, *args, domyslne_lata=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.domyslne_lata = domyslne_lata or (DEFAULT_ROK_OD, DEFAULT_ROK_DO)

    def clean_rok_od(self):
        return self.cleaned_data.get("rok_od") or self.domyslne_lata[0]

    def clean_rok_do(self):
        return self.cleaned_data.get("rok_do") or self.domyslne_lata[1]


class FilterForm(_LataOkresuMixin, forms.Form):
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
    tylko_z_publikacjami_w_okresie = forms.BooleanField(required=False, initial=True)

    def clean_search(self):
        return self.cleaned_data.get("search") or ""

    def clean_dyscyplina(self):
        return self.cleaned_data.get("dyscyplina") or ""


class DyscyplinyFilterForm(_LataOkresuMixin, forms.Form):
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
    tylko_z_publikacjami_w_okresie = forms.BooleanField(required=False, initial=True)
    wyswietlaj_nazwy = forms.BooleanField(required=False, initial=False)

    def clean_search(self):
        return self.cleaned_data.get("search") or ""


class PrzebudujForm(forms.Form):
    """Formularz przebudowy porównania; puste „Minimalny rok” = domyślny."""

    DOMYSLNY_MIN_ROK = 2022

    min_rok = forms.IntegerField(required=False, min_value=2000, max_value=2100)
    clear_existing = forms.BooleanField(required=False)

    def clean_min_rok(self):
        min_rok = self.cleaned_data.get("min_rok")
        return self.DOMYSLNY_MIN_ROK if min_rok is None else min_rok
