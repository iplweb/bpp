from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, ButtonHolder, Submit
from crispy_forms_foundation.layout import Column, Fieldset, Layout, Row
from django import forms

from bpp.util import formdefaults_html_after, formdefaults_html_before
from import_pracownikow.mapping import (
    POLA_DOCELOWE,
    POLE_POMIN,
    waliduj_mapowanie,
    zaproponuj_mapowanie,
)
from import_pracownikow.models import ImportPracownikow


class NowyImportForm(forms.ModelForm):
    class Meta:
        model = ImportPracownikow
        fields = [
            "plik_xls",
            "data_zmian_personalnych",
            "przepnij_wszystkie_prace",
        ]
        widgets = {
            # natywny date-picker przeglądarki (bez JS-owej zależności)
            "data_zmian_personalnych": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
        }

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_class = "custom"
        self.helper.form_action = "."
        self.helper.layout = Layout(
            Fieldset(
                "Wybierz parametry",
                formdefaults_html_before(self),
                Row(
                    Column("plik_xls", css_class="large-12 small-12"),
                ),
                Row(
                    Column("data_zmian_personalnych", css_class="large-6 small-12"),
                ),
                # „Przepnij wszystkie prace" to opcja groźna i rzadko potrzebna —
                # chowamy ją w domyślnie ZWINIĘTYM <details> (natywny collapsible,
                # bez JS). Input zwiniętego <details> normalnie się wysyła, a
                # confirm (po #id_przepnij_wszystkie_prace) dalej działa.
                HTML(
                    '<details class="callout secondary">'
                    '<summary><span class="fi-widget"></span> '
                    "Opcje zaawansowane — masowe przepięcie prac</summary>"
                ),
                Row(
                    Column("przepnij_wszystkie_prace", css_class="large-12 small-12"),
                ),
                HTML("</details>"),
                formdefaults_html_after(self),
            ),
            ButtonHolder(
                Submit(
                    "submit",
                    "Utwórz import",
                    css_id="id_submit",
                    css_class="submit button",
                ),
            ),
        )

        super().__init__(*args, **kwargs)


class MapowanieForm(forms.Form):
    """Dynamiczny formularz mapowania: jedno pole ``ChoiceField`` na każdy
    nagłówek pliku (klucz ``kol__<naglowek>``), prefill z auto-propozycji
    lub przekazanego ``initial_mapowanie`` (np. z profilu)."""

    zapisz_profil = forms.BooleanField(
        required=False, label="Zapisz to mapowanie jako profil"
    )
    profil_zastosowany = forms.IntegerField(required=False, widget=forms.HiddenInput())
    nazwa_profilu = forms.CharField(
        required=False, max_length=200, label="Nazwa profilu"
    )
    tworz_brakujace_jednostki = forms.BooleanField(
        required=False,
        initial=True,
        label="Twórz brakujące jednostki",
        help_text="Gdy zaznaczone, jednostki nieobecne w bazie trafią na ekran "
        "weryfikacji do utworzenia. Odznacz, aby pomijać wiersze bez dopasowanej "
        "jednostki.",
    )
    tworz_brakujace_tytuly = forms.BooleanField(
        required=False,
        initial=True,
        label="Twórz brakujące tytuły",
        help_text="Gdy zaznaczone, tytuły nieobecne w bazie trafią na ekran "
        "weryfikacji do utworzenia. Odznacz, aby pomijać niedopasowane tytuły "
        "(nowi autorzy powstaną bez tytułu).",
    )

    def __init__(self, *args, naglowki=None, initial_mapowanie=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.naglowki = naglowki or []
        # merge: auto-propozycja jako baza, profil (jeśli jest) nadpisuje —
        # dzięki temu nagłówki spoza profilu i tak dostają synonim, nie „pomiń".
        propozycja = {
            **zaproponuj_mapowanie(self.naglowki),
            **(initial_mapowanie or {}),
        }
        wybory = [(POLE_POMIN, "— pomiń —")] + [
            (k, etykieta) for k, etykieta in POLA_DOCELOWE
        ]
        for h in self.naglowki:
            self.fields[f"kol__{h}"] = forms.ChoiceField(
                choices=wybory,
                required=True,
                label=h,
                initial=propozycja.get(h, POLE_POMIN),
            )

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.add_input(
            Submit("submit", "Zapisz mapowanie i analizuj", css_class="button")
        )

    def mapowanie(self):
        """``{naglowek: pole_docelowe}`` z oczyszczonych danych."""
        return {
            h: self.cleaned_data[f"kol__{h}"]
            for h in self.naglowki
            if f"kol__{h}" in self.cleaned_data
        }

    def clean(self):
        cleaned = super().clean()
        bledy = waliduj_mapowanie(self.mapowanie())
        for e in bledy:
            self.add_error(None, e)
        if cleaned.get("zapisz_profil") and not cleaned.get("nazwa_profilu"):
            self.add_error("nazwa_profilu", "Podaj nazwę profilu, aby go zapisać.")
        return cleaned
