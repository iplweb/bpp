from django import forms
from django.core.exceptions import ValidationError

from bpp.models import Uczelnia


class UczelniaSetupForm(forms.ModelForm):
    """Form for creating the initial Uczelnia (University) configuration."""

    PBN_API_CHOICES = [
        (
            "https://pbn-micro-alpha.opi.org.pl",
            "Dostęp TESTOWY (https://pbn-micro-alpha.opi.org.pl)",
        ),
        ("https://pbn.nauka.gov.pl", "Dostęp PRODUKCYJNY (https://pbn.nauka.gov.pl)"),
    ]

    nazwa = forms.CharField(
        max_length=512,
        required=True,
        label="Nazwa uczelni",
        help_text="Pełna nazwa instytucji",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "np. Uniwersytet Lubelski"}
        ),
    )

    nazwa_dopelniacz_field = forms.CharField(
        max_length=512,
        required=True,
        label="Nazwa w dopełniaczu",
        help_text="Odmiana nazwy przez przypadki (dopełniacz)",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "np. Uniwersytetu Lubelskiego",
            }
        ),
    )

    skrot = forms.CharField(
        max_length=32,
        required=True,
        label="Skrót uczelni",
        help_text="Skrót nazwy instytucji",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "np. UL"}
        ),
    )

    pbn_api_root = forms.ChoiceField(
        choices=PBN_API_CHOICES,
        required=True,
        label="Środowisko PBN",
        help_text="Wybierz środowisko testowe lub produkcyjne",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    pbn_app_name = forms.CharField(
        max_length=128,
        required=False,
        label="Nazwa aplikacji w PBN",
        help_text="Nazwa aplikacji zarejestrowanej w systemie PBN",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Nazwa aplikacji otrzymana z PBN",
            }
        ),
    )

    pbn_app_token = forms.CharField(
        max_length=128,
        required=False,
        label="Token aplikacji w PBN",
        help_text="Token autoryzacyjny aplikacji w systemie PBN",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Token otrzymany z PBN"}
        ),
    )

    uzywaj_wydzialow = forms.BooleanField(
        required=False,
        initial=True,
        label="Używaj wydziałów",
        help_text="Czy struktura uczelni jest 3-poziomowa: uczelnia -> wydział -> jednostka?",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = Uczelnia
        fields = [
            "nazwa",
            "nazwa_dopelniacz_field",
            "skrot",
            "pbn_api_root",
            "pbn_app_name",
            "pbn_app_token",
            "uzywaj_wydzialow",
        ]

    def clean(self):
        cleaned_data = super().clean()

        if Uczelnia.objects.exists():
            raise ValidationError(
                "Uczelnia została już skonfigurowana. "
                "Kreator konfiguracji uczelni może być uruchomiony tylko raz."
            )

        return cleaned_data

    def save(self, commit=True):
        uczelnia = super().save(commit=False)

        # Set the fields that should always be True
        uczelnia.pbn_kasuj_dyscypliny_selektywnie = (
            True  # Selektywny DELETE oświadczeń per-osoba (nowy flow)
        )
        uczelnia.pbn_api_nie_wysylaj_prac_bez_pk = (
            True  # Nie wysyłaj do PBN prac z PK=0
        )
        uczelnia.pbn_api_afiliacja_zawsze_na_uczelnie = (
            True  # Wysyłaj zawsze UID uczelni jako afiliacje
        )
        uczelnia.pbn_wysylaj_bez_oswiadczen = True  # Wysyłaj prace bez oświadczeń
        uczelnia.pbn_integracja = True  # Używać integracji z PBN
        uczelnia.pbn_aktualizuj_na_biezaco = (
            True  # Włącz opcjonalną aktualizację przy edycji
        )

        if commit:
            uczelnia.save()

        return uczelnia
