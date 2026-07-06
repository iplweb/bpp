from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import ImproperlyConfigured
from reversion.admin import VersionAdmin

from ewaluacja_liczba_n.models import LiczbaNDlaUczelni
from pbn_api.exceptions import PraceSerwisoweException

from ..models import Uczelnia, Ukryj_Status_Korekty, Wydzial

# Uczelnia
from .core import BaseBppAdminMixin, RestrictDeletionToAdministracjaGroupMixin
from .helpers.constance_field_mixin import ConstanceUczelniaFieldsMixin
from .helpers.fieldsets import ADNOTACJE_FIELDSET
from .helpers.mixins import ZapiszZAdnotacjaMixin
from .helpers.site_filtered import SiteFilteredAdminMixin


class WydzialInlineForm(forms.ModelForm):
    class Meta:
        fields = ["nazwa", "skrot", "widoczny", "kolejnosc"]
        model = Wydzial
        widgets = {"kolejnosc": forms.HiddenInput}


class LiczbaNDlaUczelniInline(admin.TabularInline):
    model = LiczbaNDlaUczelni
    extra = 0

    def has_add_permission(self, request, obj):
        return False

    def has_delete_permission(self, request, obj=...):
        return False

    def has_change_permission(self, request, obj=...):
        return False

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


class UczelniaAdminForm(forms.ModelForm):
    # `theme_name` to na poziomie modelu zwykły CharField (bez `choices`),
    # więc deklarujemy je tu jako ChoiceField, a listę motywów pobieramy z
    # settings.BPP_THEMES — jedynego źródła prawdy. Dzięki temu dorzucenie
    # motywu w settings od razu pojawia się w dropdownie, bez migracji.
    theme_name = forms.ChoiceField(label="Motyw kolorystyczny")

    class Meta:
        model = Uczelnia
        # Tylko pole, które tu nadpisujemy — admin i tak regeneruje pełną
        # listę pól z fieldsets przez modelform_factory, ten Meta.fields jest
        # wtedy przesłaniany. Wystarcza do samodzielnego instancjonowania formy.
        fields = ["theme_name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["theme_name"].choices = list(settings.BPP_THEMES)

        # Multi-hosted: ``site`` jest na poziomie DB NOT NULL (migracja 0417),
        # ale to admin musi je wskazać JAWNIE — to Site wiąże uczelnię z
        # domeną (host → Site → Uczelnia), nie ma „uczelni domyślnej". Damy
        # komunikat dziedzinowy zamiast generycznego „To pole jest wymagane.".
        if "site" in self.fields:
            self.fields["site"].required = True
            self.fields["site"].error_messages["required"] = (
                "Wskaż stronę (domenę / obiekt Site) dla tej uczelni. W trybie "
                "multi-hosted to powiązanie z domeną wiąże uczelnię z jej "
                "adresem — nie istnieje „uczelnia domyślna”."
            )


class UczelniaAdmin(
    SiteFilteredAdminMixin,
    ConstanceUczelniaFieldsMixin,
    RestrictDeletionToAdministracjaGroupMixin,
    ZapiszZAdnotacjaMixin,
    BaseBppAdminMixin,
    VersionAdmin,
):
    form = UczelniaAdminForm
    list_display = ["nazwa", "nazwa_dopelniacz_field", "skrot", "pbn_uid"]

    def get_queryset(self, request):
        qs = super(SiteFilteredAdminMixin, self).get_queryset(request)
        if request.user.is_superuser:
            return qs
        uczelnia = getattr(request, "_uczelnia", None)
        if uczelnia:
            return qs.filter(pk=uczelnia.pk)
        return qs

    autocomplete_fields = ["pbn_uid", "obca_jednostka"]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "nazwa",
                    "nazwa_dopelniacz_field",
                    "skrot",
                    "site",
                    "theme_name",
                    "pbn_uid",
                    "pbn_id",
                    "favicon_ico",
                    "tytul_strony_glownej",
                    "obca_jednostka",
                )
            },
        ),
        (
            "Opcje edycji",
            {
                "classes": ("grp-collapse grp-closed",),
                "fields": (
                    "domyslnie_afiliuje",
                    "nowy_autor_z_formularza_pokazuj",
                ),
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
                    "pbn_kasuj_dyscypliny_selektywnie",
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
                    "pokazuj_praca_recenzowana",
                    "pokazuj_liczbe_cytowan_w_rankingu",
                    "pokazuj_liczbe_cytowan_na_stronie_autora",
                    "pokazuj_tabele_slotow_na_stronie_rekordu",
                    "pokazuj_raport_slotow_autor",
                    "pokazuj_raport_slotow_zerowy",
                    "pokazuj_raport_slotow_uczelnia",
                    "pokazuj_formularz_zglaszania_publikacji",
                    "pytaj_o_zgode_na_publikacje_pelnego_tekstu",
                    "pokazuj_autorow_obcych_w_przegladaniu_danych",
                    "pokazuj_autorow_bez_prac_w_przegladaniu_danych",
                    "pokazuj_zrodla_bez_prac_w_przegladaniu_danych",
                    "uzywaj_wydzialow",
                    "pokazuj_jednostki_na_pierwszej_stronie",
                    "pokazuj_wydzialy_na_pierwszej_stronie",
                    "pokazuj_siec_powiazan",
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
                    "wydruk_margines_gora",
                    "wydruk_margines_dol",
                    "wydruk_margines_lewo",
                    "wydruk_margines_prawo",
                ),
            },
        ),
        (
            "Podpowiadanie dyscyplin i punktacji",
            {
                "classes": ("grp-collapse grp-opened",),
                "fields": ("podpowiadaj_dyscypliny", "sugeruj_punktacje"),
            },
        ),
        (
            "Zgłaszanie publikacji",
            {
                "classes": ("grp-collapse grp-opened",),
                "fields": (
                    "wymagaj_logowania_zglos_publikacje",
                    "wymagaj_oplatach_artykul",
                    "wymagaj_oplatach_monografia",
                    "wymagaj_oplatach_rozdzial",
                    "wymagaj_oplatach_inne",
                ),
            },
        ),
        (
            "Ewaluacja",
            {
                "classes": ("grp-collapse grp-opened",),
                "fields": ("przydzielaj_1_slot_gdy_udzial_mniejszy",),
            },
        ),
        (
            "Struktura uczelni",
            {
                "classes": ("grp-collapse grp-closed",),
                "fields": (
                    "skrot_wydzialu_w_nazwie_jednostki",
                    "pokazuj_oswiadczenie_ken",
                ),
            },
        ),
        (
            "Integracje Google",
            {
                "classes": ("grp-collapse grp-closed",),
                "fields": (
                    "google_analytics_property_id",
                    "google_verification_code",
                ),
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
            "ORCID",
            {
                "classes": ("grp-collapse grp-closed",),
                "fields": (
                    "orcid_client_id",
                    "orcid_client_secret",
                    "orcid_sandbox",
                    "orcid_tylko_dla_pracownikow",
                ),
            },
        ),
        (
            "DSpace",
            {
                "classes": ("grp-collapse grp-closed",),
                "fields": (
                    "dspace_aktywny",
                    "dspace_api_endpoint",
                    "dspace_api_username",
                    "dspace_api_password",
                    "dspace_domyslny_jezyk_dc",
                ),
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
        if obj.site_id is None and not change:
            from django.contrib.sites.shortcuts import get_current_site

            obj.site = get_current_site(request)

        ret = super().save_model(request, obj, form, change)

        if obj.pbn_integracja:
            try:
                client = obj.pbn_client()
            except ImproperlyConfigured as e:
                messages.warning(
                    request,
                    f"Integracja z PBN jest włączona, ale konfiguracja jest niekompletna: {e}. "
                    f"Uzupełnij brakujące dane (nazwa aplikacji i token) lub wyłącz "
                    f"integrację z PBN w sekcji „Integracja z PBN API”.",
                )
                return ret

            # Wykonaj próbne pobranie rekordu z PBNu
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
