import json

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from reversion.admin import VersionAdmin

from ewaluacja_liczba_n.models import LiczbaNDlaUczelni
from pbn_api.exceptions import PraceSerwisoweException

from ..models import Uczelnia, Ukryj_Status_Korekty
from ..profil_autora import waliduj_uklad
from ..util.ssrf import waliduj_url_integracji

# Uczelnia
from .core import BaseBppAdminMixin, RestrictDeletionToAdministracjaGroupMixin
from .helpers.constance_field_mixin import ConstanceUczelniaFieldsMixin
from .helpers.fieldsets import ADNOTACJE_FIELDSET
from .helpers.mixins import ZapiszZAdnotacjaMixin
from .helpers.ror_field import czysc_ror
from .helpers.site_filtered import SiteFilteredAdminMixin
from .widgets.uklad_profilu import EdytorUkladuWidget


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
        "cerif",
    ]
    extra = 0


#: Fieldsety z konfiguracją integracji (adresy API, poświadczenia) —
#: widoczne i edytowalne wyłącznie dla superużytkownika.
FIELDSETY_INTEGRACJI = ("PBN API", "Clarivate Analytics API", "ORCID", "DSpace")

#: Sekrety integracji — w formularzu write-only (wartość nie jest
#: renderowana; puste pole przy zapisie zachowuje dotychczasową wartość).
POLA_SEKRETOW = (
    "pbn_app_token",
    "clarivate_password",
    "orcid_client_secret",
    "dspace_api_password",
)


class UczelniaAdminForm(forms.ModelForm):
    # `theme_name` to na poziomie modelu zwykły CharField (bez `choices`),
    # więc deklarujemy je tu jako ChoiceField, a listę motywów pobieramy z
    # settings.BPP_THEMES — jedynego źródła prawdy. Dzięki temu dorzucenie
    # motywu w settings od razu pojawia się w dropdownie, bez migracji.
    theme_name = forms.ChoiceField(label="Motyw kolorystyczny")

    class Meta:
        model = Uczelnia
        # Tylko pola, które tu nadpisujemy — admin i tak regeneruje pełną
        # listę pól z fieldsets przez modelform_factory, ten Meta.fields jest
        # wtedy przesłaniany. Wystarcza do samodzielnego instancjonowania formy.
        fields = ["theme_name", "uklad_profilu_autora"]
        widgets = {"uklad_profilu_autora": EdytorUkladuWidget}

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

        for pole in POLA_SEKRETOW:
            if pole in self.fields:
                self.fields[pole].widget = forms.PasswordInput(
                    render_value=False, attrs={"autocomplete": "new-password"}
                )
                self.fields[pole].required = False
                # Pusty submit = „bez zmian" — nie raportuj zmiany w historii.
                self.fields[pole].has_changed = lambda initial, data: bool(data)
                if self.instance.pk and getattr(self.instance, pole):
                    self.fields[pole].help_text = (
                        "Wartość jest zapisana i nie jest wyświetlana. "
                        "Pozostaw puste, aby jej nie zmieniać."
                    )

    def _zachowaj_sekret(self, pole):
        wartosc = self.cleaned_data.get(pole)
        if not wartosc and self.instance.pk:
            return getattr(self.instance, pole)
        return wartosc

    def clean_pbn_app_token(self):
        return self._zachowaj_sekret("pbn_app_token")

    def clean_clarivate_password(self):
        return self._zachowaj_sekret("clarivate_password")

    def clean_orcid_client_secret(self):
        return self._zachowaj_sekret("orcid_client_secret")

    def clean_dspace_api_password(self):
        return self._zachowaj_sekret("dspace_api_password")

    def _waliduj_adres(self, pole):
        wartosc = self.cleaned_data.get(pole)
        if wartosc and pole in self.changed_data:
            waliduj_url_integracji(wartosc)
        return wartosc

    def clean_pbn_api_root(self):
        return self._waliduj_adres("pbn_api_root")

    def clean_dspace_api_endpoint(self):
        return self._waliduj_adres("dspace_api_endpoint")

    def clean_uklad_profilu_autora(self):
        """Sanityzuj zserializowaną wartość edytora do poprawnej listy.

        Widget posta JSON-string (lub listę gdy JS nie wystartował);
        ``waliduj_uklad`` zrzuca nieznane/zduplikowane klucze i koryguje
        widoczność/limit. Puste = ``None`` (``rozwiaz_uklad`` to toleruje).
        """
        wartosc = self.cleaned_data.get("uklad_profilu_autora")
        if not wartosc:
            return None
        if isinstance(wartosc, str):
            try:
                wartosc = json.loads(wartosc)
            except (ValueError, TypeError):
                return None
        return waliduj_uklad(wartosc)

    def clean_ror_id(self):
        return czysc_ror(self.cleaned_data.get("ror_id"))


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
            "REST API (/api/v1/)",
            {
                "classes": ("grp-collapse grp-closed",),
                "fields": (
                    "api_v1_wlaczone",
                    "api_v1_tylko_zalogowani",
                    "api_v1_dane_bibliograficzne",
                    "api_v1_wyszukiwanie",
                    "api_v1_kafelki",
                    "api_v1_narzedzia_redaktorskie",
                ),
            },
        ),
        # Osobny fieldset, mimo że MCP czyta dane przez REST API. Wrzucony do
        # sekcji „REST API" sugerowałby, że `mcp_wlaczone` jest jednym
        # z przełączników API — a to niezależny wyłącznik: gasi /mcp, nie
        # ruszając /api/v1/ ani jego integracji.
        (
            "Serwer MCP dla asystentów AI (/mcp)",
            {
                "classes": ("grp-collapse grp-closed",),
                "description": (
                    "Warunek konieczny: serwis musi mieć prawidłowy certyfikat "
                    "SSL z kompletnym łańcuchem (certyfikat serwera + pośredni). "
                    "Przeglądarka uzupełni brakujący certyfikat pośredni sama, "
                    "asystenci AI — nie, i połączenie się nie uda."
                ),
                "fields": ("mcp_wlaczone",),
            },
        ),
        # DWA osobne fieldsety, mimo że oba dotyczą OAI-PMH. To NIE jest
        # jeden przełącznik z dodatkami: `oai_pmh_aktywny` bramkuje wyłącznie
        # /oai/ (feed oai_dc dla Primo), a `eksport_cerif_wlaczony` wyłącznie
        # /cerif-oai/. Wrzucone do wspólnej sekcji sugerowałyby redaktorowi,
        # że odznaczenie pierwszego wyłącza też drugi — a tak nie jest.
        (
            "OAI-PMH dla Primo (/oai/)",
            {
                "classes": ("grp-collapse grp-closed",),
                "fields": (
                    "oai_pmh_aktywny",
                    "oai_identyfikator_repozytorium",
                ),
            },
        ),
        (
            "Eksport CERIF / OpenAIRE (/cerif-oai/)",
            {
                "classes": ("grp-collapse grp-closed",),
                "fields": (
                    "eksport_cerif_wlaczony",
                    "eksport_cerif_osoby",
                    "eksport_cerif_kwoty",
                    "ror_id",
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
                    "zwijaj_dlugie_listy_autorow",
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
            "Profil autora (podstrona)",
            {
                "classes": ("grp-collapse grp-closed",),
                "description": (
                    "Układ podstrony autora (globalny dla uczelni): ciąg pasów "
                    "na całą szerokość albo par sekcji obok siebie. Przeciągnij "
                    "kafelki, aby zmienić kolejność; dla każdej sekcji wybierz "
                    "szerokość (pół / cała) — dwie kolejne „pół” stają obok "
                    "siebie. Odznacz, by ukryć; dla list ustaw limit pozycji."
                ),
                "fields": (
                    "uklad_profilu_autora",
                    "etykieta_profilu_uczelni",
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
        Ukryj_Status_KorektyInline,
        LiczbaNDlaUczelniInline,
    ]

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if request.user.is_superuser:
            return fieldsets
        # Konfiguracja integracji tylko dla superużytkownika. Admin buduje
        # pola formularza z fieldsetów, więc usunięte pola nie są też
        # nadpisywane przy zapisie.
        return [fs for fs in fieldsets if fs[0] not in FIELDSETY_INTEGRACJI]

    def _pola_integracji(self):
        return [
            pole
            for nazwa, opcje in self.fieldsets
            if nazwa in FIELDSETY_INTEGRACJI
            for pole in opcje["fields"]
        ]

    # Przywracanie wersji z historii (django-reversion) odtwarza wszystkie
    # pola, łącznie z konfiguracją integracji — tylko dla superużytkownika.
    def revision_view(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().revision_view(request, *args, **kwargs)

    def recover_view(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().recover_view(request, *args, **kwargs)

    def save_model(self, request, obj, form, change):
        if obj.site_id is None and not change:
            from django.contrib.sites.shortcuts import get_current_site

            obj.site = get_current_site(request)

        if change and not request.user.is_superuser:
            # Konfiguracja integracji zawsze taka, jak w bazie przed zapisem.
            zapisana = type(obj).objects.get(pk=obj.pk)
            for pole in self._pola_integracji():
                attname = obj._meta.get_field(pole).attname
                setattr(obj, attname, getattr(zapisana, attname))

        ret = super().save_model(request, obj, form, change)

        if obj.pbn_integracja and request.user.is_superuser:
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
