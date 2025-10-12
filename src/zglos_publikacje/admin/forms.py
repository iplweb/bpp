from django import forms

from zglos_publikacje.models import Zgloszenie_Publikacji


class ZwrocEmailForm(forms.ModelForm):
    przyczyna_zwrotu = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "cols": 80}),
        max_length=2000,
        help_text="Maksymalnie 2000 znaków",
    )

    class Meta:
        model = Zgloszenie_Publikacji
        fields = [
            "przyczyna_zwrotu",
        ]
