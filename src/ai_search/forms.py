from django import forms

from bpp.views.zapytanie import MODEL_CHOICES, MODEL_REKORD


class AISearchForm(forms.Form):
    model = forms.ChoiceField(
        choices=MODEL_CHOICES,
        widget=forms.RadioSelect,
        initial=MODEL_REKORD,
        label="Model do przeszukania",
    )
    pytanie = forms.CharField(
        label="Zadaj pytanie po polsku",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "np. publikacje z 2024 roku autora Kowalskiego",
                "autocomplete": "off",
            }
        ),
    )
