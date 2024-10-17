from django import forms

from ewaluacja2021.models import LiczbaNDlaUczelni
from pbn_api.exceptions import PraceSerwisoweException
from ..models import Uczelnia, Ukryj_Status_Korekty, Wydzial

# Uczelnia
from .core import BaseBppAdminMixin, RestrictDeletionToAdministracjaGroupMixin
from .helpers import ADNOTACJE_FIELDSET, ZapiszZAdnotacjaMixin

from django.contrib import admin, messages


class WydzialInlineForm(forms.ModelForm):
    class Meta:
        fields = ["nazwa", "skrot", "widoczny", "kolejnosc"]
        model = Wydzial
        widgets = {"kolejnosc": forms.HiddenInput}


class LiczbaNDlaUczelniInline(admin.TabularInline):
    model = LiczbaNDlaUczelni
    extra = 1

    class Meta:
        fields = ["dyscyplina_naukowa", "liczba_n"]


class WydzialInline(admin.TabularInline):
    classes = ["grp-collapse grp-closed grp-never-open-automatically"]
    model = Wydzial
    form = WydzialInlineForm
    extra = 0
    sortable_field_name = "kolejnosc"


class Ukryj_Status_KorektyInline(admin.StackedInline):
    model = Ukryj_Status_Korekty
    fields = [
        "status_korekty",
        "multiwyszukiwarka",
        "podglad",
        "raporty",
        "rankingi",
        "sloty",
        "api",
    ]
    extra = 0


class UczelniaAdmin(
    RestrictDeletionToAdministracjaGroupMixin,
    ZapiszZAdnotacjaMixin,
    BaseBppAdminMixin,
    admin.ModelAdmin,
):
    list_display = ["nazwa", "nazwa_dopelniacz_field", "skrot", "pbn_uid"]
    autocomplete_fields = ["pbn_uid", "obca_jednostka"]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "nazwa",
                    "nazwa_dopelniacz_field",
                    "skrot",
                    "pbn_uid",
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
            "PBN API",
            {
                "classes": ("grp-collapse grp-open",),
                "fields": (
                    "pbn_integracja",
                    "pbn_aktualizuj_na_biezaco",
                    "pbn_api_root",
                    "pbn_app_name",
                    "pbn_app_token",
                    "pbn_api_user",
                    "pbn_api_kasuj_przed_wysylka",
                    "pbn_api_nie_wysylaj_prac_bez_pk",
                    "pbn_api_afiliacja_zawsze_na_uczelnie",
                    "pbn_wysylaj_bez_oswiadczen",
                ),
            },
        ),
        (
            "Strona wizualna",
            {
                "classes": ("grp-collapse grp-closed",),
                "fields": (
                    "logo_www",
                    "logo_svg",
                    "ilosc_jednostek_na_strone",
                    "pokazuj_tylko_jednostki_nadrzedne",
                    "ranking_autorow_rozbij_domyslnie",
                    "pokazuj_punktacje_wewnetrzna",
                    "pokazuj_index_copernicus",
                    "pokazuj_punktacja_snip",
                    "pokazuj_status_korekty",
                    "pokazuj_ranking_autorow",
                    "ranking_autorow_bez_kol_naukowych",
                    "pokazuj_raport_autorow",
                    "pokazuj_raport_jednostek",
                    "pokazuj_raport_wydzialow",
                    "pokazuj_raport_uczelni",
                    "pokazuj_praca_recenzowana",
                    "pokazuj_liczbe_cytowan_w_rankingu",
                    "pokazuj_liczbe_cytowan_na_stronie_autora",
                    "pokazuj_tabele_slotow_na_stronie_rekordu",
                    "pokazuj_raport_slotow_autor",
                    "pokazuj_raport_slotow_zerowy",
                    "pokazuj_raport_slotow_uczelnia",
                    "pokazuj_formularz_zglaszania_publikacji",
                    "pokazuj_autorow_obcych_w_przegladaniu_danych",
                    "pokazuj_autorow_bez_prac_w_przegladaniu_danych",
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
                    "drukuj_oswiadczenia",
                    "drukuj_alternatywne_oswiadczenia",
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
        (
            "Zgłaszanie publikacji",
            {
                "classes": ("grp-collapse grp-opened",),
                "fields": ("wymagaj_informacji_o_oplatach",),
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
        (
            "Deklaracja dostępności",
            {
                "classes": (
                    "grp-collapse",
                    "grp-closed",
                    "grp-never-open-automatically",
                ),
                "fields": (
                    "pokazuj_deklaracje_dostepnosci",
                    "deklaracja_dostepnosci_url",
                    "deklaracja_dostepnosci_tekst",
                ),
            },
        ),
    )

    inlines = [
        WydzialInline,
        Ukryj_Status_KorektyInline,
        LiczbaNDlaUczelniInline,
    ]

    def save_model(self, request, obj, form, change):
        ret = super().save_model(request, obj, form, change)

        if obj.pbn_integracja:
            # Wykonaj próbne pobranie rekordu z PBNu
            client = obj.pbn_client()
            try:
                client.get_languages()
            except PraceSerwisoweException:
                messages.warning(
                    request,
                    "Nie można zweryfikować konfiguracji dla połączenia z PBN, gdyż po stronie PBN "
                    "trwają prace serwisowe. Prosimy spróbować później.",
                )
            except Exception as e:
                messages.warning(
                    request,
                    f"To nie błąd - to ostrzeżenie. Nie można pobrać przykładowych rekordów "
                    f"przez PBN API celem weryfikacji konfiguracji połączenia z PBNem. "
                    f"Kod błędu podczas próbnego pobrania danych z PBN: {e}. "
                    f"Jeżeli bład nie dotyczy problemów z siecią lub z autoryzacją PBN, skontaktuj się "
                    f"proszę z administratorem, gdyż konfiguracja PBN może być niekompletna. ",
                )
            return ret


admin.site.register(Uczelnia, UczelniaAdmin)
