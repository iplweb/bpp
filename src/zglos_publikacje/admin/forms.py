from django import forms

from zglos_publikacje.models import Zgloszenie_Publikacji


class ZwrocEmailForm(forms.ModelForm):
    class Meta:
        model = Zgloszenie_Publikacji
        fields = [
            "przyczyna_zwrotu",
        ]
