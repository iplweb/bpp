from dal import autocomplete
from django import forms

from bpp.models import Zrodlo


class PrzemapowaZrodloForm(forms.Form):
    """Formularz do przemapowania publikacji z jednego źródła do drugiego."""

    zrodlo_docelowe = forms.ModelChoiceField(
        queryset=Zrodlo.objects.all(),
        label="Źródło docelowe",
        help_text="Wybierz źródło, do którego chcesz przemapować wszystkie publikacje",
        widget=autocomplete.ModelSelect2(url="bpp:przemapuj-zrodlo-autocomplete"),
        required=True,
    )

    wyslac_do_pbn = forms.BooleanField(
        label="Wyślij publikacje do kolejki PBN",
        help_text=(
            "Zaznacz to pole aby automatycznie dodać wszystkie przemapowane publikacje "
            "do kolejki eksportu PBN. Publikacje zostaną wysłane do PBN w tle."
        ),
        initial=True,
        required=False,
    )

    potwierdzenie = forms.BooleanField(
        label="Potwierdzam przemapowanie",
        help_text="Zaznacz to pole aby potwierdzić, że chcesz przemapować wszystkie publikacje",
        required=True,
    )

    def __init__(self, *args, zrodlo_zrodlowe=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.zrodlo_zrodlowe = zrodlo_zrodlowe

    def clean_zrodlo_docelowe(self):
        zrodlo_docelowe = self.cleaned_data.get("zrodlo_docelowe")

        # Walidacja: źródło docelowe nie może być tym samym co źródłowe
        if self.zrodlo_zrodlowe and zrodlo_docelowe:
            if zrodlo_docelowe.pk == self.zrodlo_zrodlowe.pk:
                raise forms.ValidationError(
                    "Źródło docelowe nie może być takie samo jak źródło źródłowe. "
                    "Wybierz inne źródło."
                )

        return zrodlo_docelowe
