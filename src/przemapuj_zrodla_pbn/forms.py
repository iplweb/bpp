from django import forms

from bpp.models import Zrodlo


class PrzeMapowanieZrodlaForm(forms.Form):
    """Formularz do przemapowania źródła."""

    TYP_ZRODLO = "zrodlo"
    TYP_JOURNAL = "journal"

    TYP_CHOICES = [
        (TYP_ZRODLO, "Źródło z BPP"),
        (TYP_JOURNAL, "Nowe źródło z PBN"),
    ]

    typ_wyboru = forms.ChoiceField(
        choices=TYP_CHOICES,
        widget=forms.HiddenInput(),
        required=False,
        initial=TYP_ZRODLO,
    )

    zrodlo_docelowe = forms.ModelChoiceField(
        queryset=Zrodlo.objects.none(),  # Będzie ustawione w __init__
        label="Źródło docelowe (z BPP)",
        help_text="Wybierz źródło które już istnieje w BPP",
        required=False,
        widget=forms.RadioSelect,
        empty_label=None,
    )

    journal_docelowy = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        help_text="ID journala z PBN który zostanie utworzony jako nowe źródło",
    )

    def __init__(
        self,
        *args,
        zrodlo_skasowane=None,
        sugerowane_zrodla=None,
        sugerowane_journale=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        if sugerowane_zrodla is not None:
            # Ustaw queryset na sugerowane źródła
            self.fields["zrodlo_docelowe"].queryset = sugerowane_zrodla
        elif zrodlo_skasowane is not None:
            # Fallback: wszystkie źródła oprócz skasowanego
            self.fields["zrodlo_docelowe"].queryset = Zrodlo.objects.exclude(
                pk=zrodlo_skasowane.pk
            )
        else:
            # Domyślnie: wszystkie źródła
            self.fields["zrodlo_docelowe"].queryset = Zrodlo.objects.all()

        self.zrodlo_skasowane = zrodlo_skasowane
        self.sugerowane_journale = sugerowane_journale or []

    def clean(self):
        cleaned_data = super().clean()
        typ_wyboru = cleaned_data.get("typ_wyboru")
        zrodlo_docelowe = cleaned_data.get("zrodlo_docelowe")
        journal_docelowy = cleaned_data.get("journal_docelowy")

        if typ_wyboru == self.TYP_ZRODLO:
            if not zrodlo_docelowe:
                raise forms.ValidationError("Wybierz źródło docelowe z BPP")
        elif typ_wyboru == self.TYP_JOURNAL:
            if not journal_docelowy:
                raise forms.ValidationError("Wybierz źródło docelowe z PBN")
        else:
            raise forms.ValidationError("Nieprawidłowy typ wyboru")

        return cleaned_data
