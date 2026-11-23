from django import forms
from django.utils import timezone

from .models import UzgodnienieZPBN

#: Najwcześniejszy rok, jaki przyjmujemy (PBN nie ma starszych profili).
ROK_MIN = 1990


class StartForm(forms.Form):
    rok_od = forms.IntegerField(label="Rok od", min_value=ROK_MIN)
    rok_do = forms.IntegerField(label="Rok do", min_value=ROK_MIN)
    tryb = forms.ChoiceField(choices=UzgodnienieZPBN.Tryb.choices)
    #: Tylko dla pobrania: pobrać ponownie także listę prac z profilu
    #: instytucji, choć jest świeża (domyślnie bierzemy ostatnio pobraną).
    caly_profil = forms.BooleanField(required=False)

    def clean(self):
        dane = super().clean()
        rok_od, rok_do = dane.get("rok_od"), dane.get("rok_do")
        if rok_od and rok_do:
            if rok_od > rok_do:
                raise forms.ValidationError(
                    "„Rok od” nie może być późniejszy niż „Rok do”."
                )
            if rok_do > timezone.now().year + 1:
                raise forms.ValidationError("„Rok do” jest zbyt odległy.")
        return dane
