from django import forms
from django.core.management import call_command
from django.db import transaction
from ..models import Uczelnia, Ukryj_Status_Korekty, Wydzial
from .core import CommitedModelAdmin, RestrictDeletionToAdministracjaGroupMixin
from .helpers import ADNOTACJE_FIELDSET, ZapiszZAdnotacjaMixin

from django.contrib import admin

# Uczelnia


class WydzialInlineForm(forms.ModelForm):
    class Meta:
        fields = ["nazwa", "skrot", "widoczny", "kolejnosc"]
        model = Wydzial
        widgets = {"kolejnosc": forms.HiddenInput}


class WydzialInline(admin.TabularInline):
    model = Wydzial
    form = WydzialInlineForm
    extra = 0
    sortable_field_name = "kolejnosc"


class Ukryj_Status_KorektyInline(admin.StackedInline):
    model = Ukryj_Status_Korekty
    fields = [
        "status_korekty",
        "multiwyszukiwarka",
        "raporty",
        "rankingi",
        "sloty",
        "api",
    ]
    extra = 0


class UczelniaAdmin(
    RestrictDeletionToAdministracjaGroupMixin, ZapiszZAdnotacjaMixin, CommitedModelAdmin
):
    list_display = ["nazwa", "nazwa_dopelniacz_field", "skrot", "pbn_id"]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "nazwa",
                    "nazwa_dopelniacz_field",
                    "skrot",
                    "pbn_id",
                    "favicon_ico",
                    "obca_jednostka",
                )
            },
        ),
        (
            "Opcje edycji",
            {
                "classes": ("grp-collapse grp-closed",),
                "fields": ("domyslnie_afiliuje",),
            },
        ),
        (
            "Strona wizualna",
            {
                "classes": ("grp-collapse grp-closed",),
                "fields": (
                    "logo_www",
                    "logo_svg",
                    "ranking_autorow_rozbij_domyslnie",
                    "pokazuj_punktacje_wewnetrzna",
                    "pokazuj_index_copernicus",
                    "pokazuj_punktacja_snip",
                    "pokazuj_status_korekty",
                    "pokazuj_ranking_autorow",
                    "pokazuj_raport_autorow",
                    "pokazuj_raport_jednostek",
                    "pokazuj_raport_wydzialow",
                    "pokazuj_raport_dla_komisji_centralnej",
                    "pokazuj_praca_recenzowana",
                    "pokazuj_liczbe_cytowan_w_rankingu",
                    "pokazuj_liczbe_cytowan_na_stronie_autora",
                    "pokazuj_tabele_slotow_na_stronie_rekordu",
                    "pokazuj_raport_slotow_autor",
                    "pokazuj_raport_slotow_zerowy",
                    "pokazuj_raport_slotow_uczelnia",
                    "wyszukiwanie_rekordy_na_strone_anonim",
                    "wyszukiwanie_rekordy_na_strone_zalogowany",
                    "sortuj_jednostki_alfabetycznie",
                    "metoda_do_roku_formularze",
                ),
            },
        ),
        (
            "Wydruki",
            {
                "classes": ("grp-collapse grp-closed",),
                "fields": (
                    "wydruk_logo",
                    "wydruk_logo_szerokosc",
                    "wydruk_parametry_zapytania",
                ),
            },
        ),
        (
            "Podpowiadanie dyscyplin",
            {
                "classes": ("grp-collapse grp-opened",),
                "fields": ("podpowiadaj_dyscypliny",),
            },
        ),
        ADNOTACJE_FIELDSET,
        (
            "Clarivate Analytics API",
            {
                "classes": ("grp-collapse grp-closed",),
                "fields": ("clarivate_username", "clarivate_password"),
            },
        ),
    )

    inlines = [WydzialInline, Ukryj_Status_KorektyInline]

    def save_model(self, request, obj, form, change):
        """Przy zmianie parametru 'sortuj_jednostki_alfabetycznie' wywołaj polecenie
        'reorder' dla bpp.Jednostki z django-adminsortable2."""

        if "sortuj_jednostki_alfabetycznie" in form.changed_data:
            if form.cleaned_data["sortuj_jednostki_alfabetycznie"] is True:
                transaction.on_commit(
                    lambda: call_command("reorder", "bpp.Jednostka", "bpp.Wydzial")
                )

        return super(UczelniaAdmin, self).save_model(request, obj, form, change)


admin.site.register(Uczelnia, UczelniaAdmin)
