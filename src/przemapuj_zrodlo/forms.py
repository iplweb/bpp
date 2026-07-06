from dal import autocomplete
from django import forms

from bpp.models import Zrodlo


class PrzemapowaZrodloForm(forms.Form):
    """Formularz do przemapowania publikacji z jednego źródła do drugiego."""

    zrodlo_docelowe = forms.ModelChoiceField(
        queryset=Zrodlo.objects.all(),
        label="Źródło docelowe",
        help_text=(
            '<span class="form-help-text-block">'
            "Wybierz źródło, do którego chcesz przemapować wszystkie publikacje"
            "</span>"
        ),
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

    @staticmethod
    def _mnisw_id(zrodlo):
        """MNiSW ID źródła ministerialnego (pbn_uid z mniswId, status != DELETED),
        albo None gdy źródło nie jest „ministerialne"."""
        if zrodlo is None:
            return None
        pbn = getattr(zrodlo, "pbn_uid", None)
        if pbn and pbn.mniswId and pbn.status != "DELETED":
            return pbn.mniswId
        return None

    def clean_zrodlo_docelowe(self):
        zrodlo_docelowe = self.cleaned_data.get("zrodlo_docelowe")

        if not (self.zrodlo_zrodlowe and zrodlo_docelowe):
            return zrodlo_docelowe

        # Walidacja: źródło docelowe nie może być tym samym co źródłowe
        if zrodlo_docelowe.pk == self.zrodlo_zrodlowe.pk:
            raise forms.ValidationError(
                "Źródło docelowe nie może być takie samo jak źródło źródłowe. "
                "Wybierz inne źródło."
            )

        # Źródło ministerialne (z MNiSW ID) można przemapować WYŁĄCZNIE na
        # źródło o tym samym MNiSW ID — wtedy to deduplikacja tego samego
        # czasopisma ministerialnego (bezpieczne dla punktacji; PBN i tak ma
        # publikacje pod tym czasopismem). Przenoszenie publikacji z czasopisma
        # ministerialnego do INNEGO jest zablokowane.
        src_mnisw = self._mnisw_id(self.zrodlo_zrodlowe)
        if src_mnisw is not None and self._mnisw_id(zrodlo_docelowe) != src_mnisw:
            raise forms.ValidationError(
                f'Źródło "{self.zrodlo_zrodlowe.nazwa}" jest na oficjalnej liście '
                f"ministerstwa (MNiSW ID: {src_mnisw}). Można je przemapować "
                f"tylko na źródło o TYM SAMYM MNiSW ID (deduplikacja tego samego "
                f"czasopisma)."
            )

        return zrodlo_docelowe
