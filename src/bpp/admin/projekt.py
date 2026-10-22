"""Admin encji projektu badawczego, jego finansowania i grantodawców.

Wprowadzanie danych o projektach odbywa się z poziomu projektu: zespół
i źródła finansowania są inline'ami, bo w oderwaniu od projektu nie mają
sensu. Słownik instytucji finansujących jest osobnym adminem — jest
współdzielony między projektami i uzupełniany rzadko.
"""

from django import forms
from django.contrib import admin

from bpp.models import (
    Finansowanie,
    Instytucja_Finansujaca,
    Projekt,
    Projekt_Autor,
)

from .core import BaseBppAdminMixin
from .helpers.fieldsets import ADNOTACJE_FIELDSET
from .helpers.mixins import ZapiszZAdnotacjaMixin


class Projekt_AutorForm(forms.ModelForm):
    """Wyłącza walidację ``UniqueConstraint`` na poziomie pojedynczego wiersza.

    Django 6.1 dodało ``BaseModelForm.validate_constraints()`` (w 5.2 ta
    metoda jeszcze nie istniała) — każdy formularz sam odpytuje bazę o
    naruszenie constraintów modelu. W inline'ie to daje fałszywy alarm przy
    podmianie kierownika w jednym zapisie: stary wiersz jest oznaczony
    ``DELETE``, ale wciąż siedzi w bazie, więc nowy kierownik „narusza"
    ``projekt_jeden_kierownik``, choć po zapisie stan będzie poprawny.

    Django koordynuje to między formularzami tylko dla unikalności —
    ``BaseModelFormSet.validate_unique()`` odsiewa ``self.deleted_forms``.
    Dla constraintów odpowiednika nie ma, więc odsiew robimy sami:
    ``Projekt_AutorFormSet.clean()`` niżej liczy kierowników pomijając wiersze
    z ``DELETE``, a constraint w bazie zostaje jako ostatnia linia obrony.
    Netto: zachowanie sprzed 6.1, tyle że teraz świadomie.
    """

    def clean(self):
        dane = super().clean()
        # ``BaseModelForm.clean()`` ustawia tę flagę na True; gasimy ją po
        # nim, ale przed ``_post_clean()``, które ją odczytuje.
        self._validate_constraints = False
        return dane


class Projekt_AutorFormSet(forms.BaseInlineFormSet):
    """Duplikuje bazowy ``UniqueConstraint`` na „jeden kierownik na projekt”.

    Baza i tak nie przepuści dwóch kierowników, ale rzucony przez nią
    ``IntegrityError`` kończy się dla redaktora pięćsetką i utratą całego
    wypełnionego formularza. Tutaj ten sam warunek daje czytelny komunikat
    walidacji. Constraint w bazie zostaje jako ostatnia linia obrony —
    formset widzi wyłącznie własne wiersze, a dane wchodzą też importem
    i przez ORM.
    """

    def clean(self):
        super().clean()
        kierownicy = 0
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            if form.cleaned_data.get("rola") == Projekt_Autor.ROLA_KIEROWNIK:
                kierownicy += 1
        if kierownicy > 1:
            raise forms.ValidationError("Projekt może mieć tylko jednego kierownika.")


class Projekt_AutorInline(admin.TabularInline):
    model = Projekt_Autor
    form = Projekt_AutorForm
    formset = Projekt_AutorFormSet
    extra = 0
    autocomplete_fields = ["autor"]


class FinansowanieInline(admin.TabularInline):
    model = Finansowanie
    extra = 0
    autocomplete_fields = ["instytucja"]
    fields = [
        "typ",
        "instytucja",
        "nazwa_programu",
        "numer_umowy",
        "kwota",
        "waluta",
        "grant_doi",
    ]


@admin.register(Projekt)
class ProjektAdmin(ZapiszZAdnotacjaMixin, BaseBppAdminMixin, admin.ModelAdmin):
    list_display = [
        "tytul",
        "akronim",
        "status",
        "data_rozpoczecia",
        "data_zakonczenia",
        "jednostka",
    ]
    list_filter = ["status", "jednostka", "dyscypliny"]
    # ``search_fields`` jest tu wymagane nie tylko dla wygody: bez niego
    # ``autocomplete_fields = ["projekt"]`` w adminie grantu wywala się
    # na admin.E040.
    search_fields = ["tytul", "tytul_en", "akronim", "abstrakt"]
    autocomplete_fields = ["jednostka"]
    filter_horizontal = ["dyscypliny"]
    inlines = [Projekt_AutorInline, FinansowanieInline]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "tytul",
                    "tytul_en",
                    "akronim",
                    "status",
                    "jednostka",
                    "data_rozpoczecia",
                    "data_zakonczenia",
                    "strona_www",
                )
            },
        ),
        (
            "Opis",
            {
                "classes": ("grp-collapse grp-open",),
                "fields": (
                    "abstrakt",
                    "abstrakt_en",
                    "dyscypliny",
                    "slowa_kluczowe",
                    "slowa_kluczowe_eng",
                ),
            },
        ),
        ADNOTACJE_FIELDSET,
    )


@admin.register(Instytucja_Finansujaca)
class Instytucja_FinansujacaAdmin(
    ZapiszZAdnotacjaMixin, BaseBppAdminMixin, admin.ModelAdmin
):
    list_display = ["nazwa", "akronim", "kraj", "ror_id", "fundref_id"]
    list_filter = ["kraj"]
    search_fields = ["nazwa", "nazwa_en", "akronim", "ror_id", "fundref_id"]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "nazwa",
                    "nazwa_en",
                    "akronim",
                    "kraj",
                    "strona_www",
                )
            },
        ),
        (
            "Identyfikatory zewnętrzne 🌐",
            {
                "classes": ("grp-collapse grp-open",),
                "fields": (
                    "ror_id",
                    "fundref_id",
                ),
            },
        ),
        ADNOTACJE_FIELDSET,
    )
