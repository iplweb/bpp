from django import forms


class PunktacjaZrodlaFilterForm(forms.Form):
    """Formularz filtrowania po punktacji źródła."""

    PUNKTACJA_CHOICES = [
        ("", "Wszystkie"),
        ("0-100", "0-100 punktów"),
        ("100-140", "100-140 punktów"),
        ("140-200", "140-200 punktów"),
        ("200+", "200+ punktów"),
    ]

    punktacja_zrodla = forms.ChoiceField(
        choices=PUNKTACJA_CHOICES,
        required=False,
        label="Punktacja źródła",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
