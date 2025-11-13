from dal import autocomplete
from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from djangoql.admin import DjangoQLSearchMixin
from mptt.forms import TreeNodeChoiceField
from taggit.forms import TextareaTagWidget

from bpp.admin import helpers
from bpp.admin.filters import (
    BezJakichkolwiekDyscyplinFilter,
    CalkowitaLiczbaAutorowFilter,
    DOIUstawioneFilter,
    JestWydawnictwemNadrzednymDlaFilter,
    LiczbaZnakowFilter,
    MaKonferencjeFilter,
    MaWydawnictwoNadrzedneFilter,
    OstatnioZmienionePrzezFilter,
    PBN_UID_IDObecnyFilter,
    UtworzonePrzezFilter,
)
from bpp.admin.helpers import fieldsets
from bpp.admin.helpers.widgets import COMMA_DECIMAL_FIELD_OVERRIDE
from bpp.models import (
    Charakter_Formalny,
    Wydawca,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
    Wydawnictwo_Zwarte_Streszczenie,
    Wydawnictwo_Zwarte_Zewnetrzna_Baza_Danych,
)
from bpp.models.konferencja import Konferencja
from bpp.models.seria_wydawnicza import Seria_Wydawnicza
from crossref_bpp.mixins import AdminCrossrefAPIMixin, AdminCrossrefPBNAPIMixin
from dynamic_columns.mixins import DynamicColumnsMixin
from import_common.normalization import normalize_isbn
from pbn_api.models import Publication

from .actions import (
    ustaw_po_korekcie,
    ustaw_przed_korekta,
    ustaw_w_trakcie_korekty,
    wyslij_do_pbn,
    wyslij_do_pbn_w_tle,
)
from .core import BaseBppAdminMixin, KolumnyZeSkrotamiMixin, generuj_inline_dla_autorow
from .crossref_api_helpers import (
    KorzystaZCrossRefAPIStreszczenieInlineMixin,
    UzupelniajWstepneDanePoCrossRefAPIMixin,
)
from .element_repozytorium import Element_RepozytoriumInline
from .grant import Grant_RekorduInline
from .helpers import (
    poszukaj_duplikatu_pola_www_i_ewentualnie_zmien,
    sprawdz_duplikaty_www_doi,
)
from .helpers.mixins import OptionalPBNSaveMixin, RestrictDeletionWhenPBNUIDSetMixin
from .nagroda import NagrodaInline

# Proste tabele
from .wydawnictwo_ciagle import CleanDOIWWWPublicWWWMixin
from .xlsx_export import resources
from .xlsx_export.mixins import EksportDanychZFormatowanieMixin, ExportActionsMixin
from .zglos_publikacje_helpers import UzupelniajWstepneDanePoNumerzeZgloszeniaMixin


class Wydawnictwo_Zwarte_StreszczenieInline(
    KorzystaZCrossRefAPIStreszczenieInlineMixin, admin.StackedInline
):
    model = Wydawnictwo_Zwarte_Streszczenie
    extra = 0
    fields = ["jezyk_streszczenia", "streszczenie"]


class Wydawnictwo_ZwarteAdmin_Baza(BaseBppAdminMixin, admin.ModelAdmin):
    formfield_overrides = {
        **helpers.widgets.NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW,
        **COMMA_DECIMAL_FIELD_OVERRIDE,
    }

    actions = [
        ustaw_po_korekcie,
        ustaw_w_trakcie_korekty,
        ustaw_przed_korekta,
        wyslij_do_pbn,
        wyslij_do_pbn_w_tle,
    ]

    list_display_always = [
        "tytul_oryginalny",
    ]

    list_display_default = [
        "wydawnictwo",
        "doi",
        "wydawnictwo_nadrzedne_col",
        "rok",
        "typ_kbn__skrot",
        "charakter_formalny__skrot",
        "ostatnio_zmieniony",
    ]

    list_display_allowed = "__all__"

    search_fields = [
        "tytul",
        "tytul_oryginalny",
        "szczegoly",
        "uwagi",
        "informacje",
        "slowa_kluczowe__name",
        "rok",
        "isbn",
        "id",
        "wydawca__nazwa",
        "wydawca_opis",
        "redakcja",
        "adnotacje",
        "liczba_znakow_wydawniczych",
        "wydawnictwo_nadrzedne__tytul_oryginalny",
        "konferencja__nazwa",
        "liczba_znakow_wydawniczych",
        "doi",
        "pbn_uid__pk",
    ]

    list_filter = [
        "status_korekty",
        "recenzowana",
        "typ_kbn",
        "charakter_formalny",
        "informacja_z",
        "jezyk",
        LiczbaZnakowFilter,
        "rok",
        JestWydawnictwemNadrzednymDlaFilter,
        MaWydawnictwoNadrzedneFilter,
        MaKonferencjeFilter,
        DOIUstawioneFilter,
        "weryfikacja_punktacji",
        "nie_eksportuj_przez_api",
        OstatnioZmienionePrzezFilter,
        UtworzonePrzezFilter,
        PBN_UID_IDObecnyFilter,
        BezJakichkolwiekDyscyplinFilter,
    ]

    # Usunąć przed wcomitowaniem

    # fieldsets = (
    #     ('Wydawnictwo zwarte', {
    #         'fields':
    #             DWA_TYTULY
    #             + MODEL_ZE_SZCZEGOLAMI
    #             + ('miejsce_i_rok', 'wydawnictwo',)
    #             + MODEL_Z_ISBN
    #             + MODEL_Z_ROKIEM
    #     }),
    #     EKSTRA_INFORMACJE_WYDAWNICTWO_ZWARTE_FIELDSET,
    #     MODEL_TYPOWANY_FIELDSET,
    #     MODEL_PUNKTOWANY_FIELDSET,
    #     POZOSTALE_MODELE_FIELDSET,
    #     ADNOTACJE_Z_DATAMI_ORAZ_PBN_FIELDSET)

    def wydawnictwo_nadrzedne_col(self, obj):
        try:
            return obj.wydawnictwo_nadrzedne.tytul_oryginalny
        except Wydawnictwo_Zwarte.DoesNotExist:
            return ""
        except AttributeError:
            return ""

    wydawnictwo_nadrzedne_col.short_description = "Wydawnictwo nadrzędne"
    wydawnictwo_nadrzedne_col.admin_order_field = (
        "wydawnictwo_nadrzedne__tytul_oryginalny"
    )


class Wydawnictwo_ZwarteForm(
    helpers.mixins.Wycinaj_W_z_InformacjiMixin,
    CleanDOIWWWPublicWWWMixin,
    forms.ModelForm,
):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._warnings = []

    def _sprawdz_isbn_z_nadrzednym(
        self, rekord_isbn, rekord_e_isbn, nadrzedne_isbn_list, nazwa_nadrzednego
    ):
        """
        Sprawdza zgodność ISBN rekordu z ISBN wydawnictwa nadrzędnego.

        Args:
            rekord_isbn: ISBN rekordu
            rekord_e_isbn: E-ISBN rekordu
            nadrzedne_isbn_list: lista ISBN-ów nadrzędnych do sprawdzenia
            nazwa_nadrzednego: nazwa wydawnictwa nadrzędnego (dla komunikatów)

        Returns:
            tuple: (is_valid: bool, warning_message: str|None)
                - is_valid: True jeśli walidacja przeszła, False jeśli błąd
                - warning_message: None lub komunikat ostrzeżenia
        """
        # Normalizuj ISBN rekordu
        norm_isbn = normalize_isbn(rekord_isbn)
        norm_e_isbn = normalize_isbn(rekord_e_isbn)

        # Normalizuj ISBN nadrzędnych
        norm_nadrzedne = [normalize_isbn(isbn) for isbn in nadrzedne_isbn_list if isbn]

        # Przypadek 1: rekord nie ma żadnego ISBN - pozwól bez ostrzeżenia
        if not norm_isbn and not norm_e_isbn:
            return (True, None)

        # Przypadek 2: nadrzędne nie ma żadnego ISBN - pozwól z ostrzeżeniem
        if not any(norm_nadrzedne):
            return (
                True,
                f"Wydawnictwo nadrzędne '{nazwa_nadrzednego}' nie ma uzupełnionego pola ISBN",
            )

        # Przypadek 3: sprawdź zgodność - jeśli którykolwiek ISBN rekordu pasuje do któregokolwiek ISBN nadrzędnego
        rekord_isbns = [i for i in [norm_isbn, norm_e_isbn] if i]
        if any(
            r_isbn == n_isbn
            for r_isbn in rekord_isbns
            for n_isbn in norm_nadrzedne
            if n_isbn
        ):
            return (True, None)

        # Przypadek 4: niezgodność - nie pozwól na zapis
        isbn_display = rekord_isbn or rekord_e_isbn
        nadrzedne_isbn_display = ", ".join(
            [isbn for isbn in nadrzedne_isbn_list if isbn]
        )
        return (
            False,
            f"ISBN rekordu ({isbn_display}) nie zgadza się z ISBN wydawnictwa nadrzędnego ({nadrzedne_isbn_display})",
        )

    wydawnictwo_nadrzedne = forms.ModelChoiceField(
        required=False,
        queryset=Wydawnictwo_Zwarte.objects.all(),
        label="Wydawnictwo nadrzędne",
        widget=autocomplete.ModelSelect2(
            url="bpp:wydawnictwo-nadrzedne-autocomplete",
            attrs=dict(style="width: 746px;"),
        ),
    )

    wydawnictwo_nadrzedne_w_pbn = forms.ModelChoiceField(
        required=False,
        queryset=Publication.objects.all(),
        label="Wydawnictwo nadrzędne w PBN",
        help_text="""Jeżeli ten rekord to rozdział, a redakcja książki nie jest z obecnej instytucji, możesz uzupełnić
    to pole, aby móc wysłać 'swój' rozdział do PBNu i jednocześnie nie musieć dodawać do bazy BPP 'cudzej' książki.
    Innymi słowy, jeżeli 'okładki' dla Twojego rozdziału znajdują się w PBN i nie chcesz ich dodawać do BPP,
    to skorzystaj z tego pola. Jeżeli jednak wypełnisz to pole, to musisz pozostawić oryginalne
    'Wydawnictwo nadrzędne' puste. """,
        widget=autocomplete.ModelSelect2(
            url="bpp:wydawnictwo-nadrzedne-w-pbn-autocomplete",
            attrs=dict(style="width: 746px;"),
        ),
    )

    wydawca = forms.ModelChoiceField(
        required=False,
        queryset=Wydawca.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="bpp:wydawca-autocomplete", attrs=dict(style="width: 746px;")
        ),
    )

    konferencja = forms.ModelChoiceField(
        required=False,
        queryset=Konferencja.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="bpp:konferencja-autocomplete", attrs=dict(style="width: 746px;")
        ),
    )

    pbn_uid = forms.ModelChoiceField(
        label="Odpowiednik w PBN",
        required=False,
        queryset=Publication.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="bpp:publication-autocomplete",
            attrs=dict(style="width: 746px;"),
        ),
    )

    seria_wydawnicza = forms.ModelChoiceField(
        required=False,
        queryset=Seria_Wydawnicza.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="bpp:seria-wydawnicza-autocomplete",
            attrs=dict(style="width: 746px;"),
        ),
    )

    charakter_formalny = TreeNodeChoiceField(
        required=True, queryset=Charakter_Formalny.objects.all()
    )

    status_korekty = helpers.mixins.DomyslnyStatusKorektyMixin.status_korekty

    def clean(self):
        cleaned_data = super().clean()

        isbn = cleaned_data.get("isbn")
        e_isbn = cleaned_data.get("e_isbn")
        wydawnictwo_nadrzedne = cleaned_data.get("wydawnictwo_nadrzedne")
        wydawnictwo_nadrzedne_w_pbn = cleaned_data.get("wydawnictwo_nadrzedne_w_pbn")

        # Walidacja ISBN dla wydawnictwo_nadrzedne
        if wydawnictwo_nadrzedne:
            nadrzedne_isbns = [wydawnictwo_nadrzedne.isbn, wydawnictwo_nadrzedne.e_isbn]
            is_valid, message = self._sprawdz_isbn_z_nadrzednym(
                isbn, e_isbn, nadrzedne_isbns, wydawnictwo_nadrzedne.tytul_oryginalny
            )

            if not is_valid:
                raise ValidationError({"isbn": message, "e_isbn": message})

            if message:
                self._warnings.append(message)

        # Walidacja ISBN dla wydawnictwo_nadrzedne_w_pbn
        if wydawnictwo_nadrzedne_w_pbn:
            nadrzedne_isbns = [wydawnictwo_nadrzedne_w_pbn.isbn]
            is_valid, message = self._sprawdz_isbn_z_nadrzednym(
                isbn, e_isbn, nadrzedne_isbns, str(wydawnictwo_nadrzedne_w_pbn)
            )

            if not is_valid:
                raise ValidationError({"isbn": message, "e_isbn": message})

            if message:
                self._warnings.append(message)

        return cleaned_data

    class Meta:
        model = Wydawnictwo_Zwarte
        fields = [
            "tekst_przed_pierwszym_autorem",
            "tekst_po_ostatnim_autorze",
            "liczba_znakow_wydawniczych",
            "adnotacje",
            "pbn_id",
            "issn",
            "e_issn",
            "isbn",
            "e_isbn",
            "informacja_z",
            "tytul_oryginalny",
            "tytul",
            "status_korekty",
            "rok",
            "www",
            "dostep_dnia",
            "public_www",
            "public_dostep_dnia",
            "pubmed_id",
            "pmc_id",
            "doi",
            "recenzowana",
            "impact_factor",
            "punkty_kbn",
            "index_copernicus",
            "punktacja_wewnetrzna",
            "punktacja_snip",
            "weryfikacja_punktacji",
            "typ_kbn",
            "jezyk",
            "jezyk_alt",
            "jezyk_orig",
            "slowa_kluczowe_eng",
            "informacje",
            "szczegoly",
            "uwagi",
            "strony",
            "tom",
            "charakter_formalny",
            "legacy_data",
            "praca_wybitna",
            "uzasadnienie_wybitnosci",
            "pbn_uid",
            "opl_pub_cost_free",
            "opl_pub_research_potential",
            "opl_pub_research_or_development_projects",
            "opl_pub_other",
            "opl_pub_amount",
            "seria_wydawnicza",
            "numer_w_serii",
            "konferencja",
            "openaccess_wersja_tekstu",
            "openaccess_licencja",
            "openaccess_czas_publikacji",
            "openaccess_ilosc_miesiecy",
            "openaccess_data_opublikowania",
            "liczba_cytowan",
            "numer_odbitki",
            "nie_eksportuj_przez_api",
            "miejsce_i_rok",
            "wydawca",
            "wydawca_opis",
            "oznaczenie_wydania",
            "redakcja",
            "openaccess_tryb_dostepu",
            "wydawnictwo_nadrzedne",
            "wydawnictwo_nadrzedne_w_pbn",
            "calkowita_liczba_autorow",
            "calkowita_liczba_redaktorow",
            "slowa_kluczowe",
        ]
        widgets = {
            "strony": forms.TextInput(attrs=dict(style="width: 150px")),
            "tom": forms.TextInput(attrs=dict(style="width: 150px")),
            "slowa_kluczowe": TextareaTagWidget(attrs={"rows": 2}),
        }


class Wydawnictwo_Zwarte_Zewnetrzna_Baza_DanychForm(forms.ModelForm):
    class Meta:
        fields = ["baza", "info"]


class Wydawnictwo_Zwarte_Zewnetrzna_Baza_DanychInline(admin.StackedInline):
    model = Wydawnictwo_Zwarte_Zewnetrzna_Baza_Danych
    extra = 0
    form = Wydawnictwo_Zwarte_Zewnetrzna_Baza_DanychForm


class Wydawnictwo_ZwarteAdmin(
    DjangoQLSearchMixin,
    KolumnyZeSkrotamiMixin,
    helpers.mixins.AdnotacjeZDatamiOrazPBNMixin,
    OptionalPBNSaveMixin,
    EksportDanychZFormatowanieMixin,
    ExportActionsMixin,
    UzupelniajWstepneDanePoNumerzeZgloszeniaMixin,
    UzupelniajWstepneDanePoCrossRefAPIMixin,
    DynamicColumnsMixin,
    AdminCrossrefAPIMixin,
    AdminCrossrefPBNAPIMixin,
    RestrictDeletionWhenPBNUIDSetMixin,
    Wydawnictwo_ZwarteAdmin_Baza,
):
    change_list_template = "admin/bpp/wydawnictwo_zwarte/change_list.html"
    import_export_change_list_template = "admin/bpp/wydawnictwo_zwarte/change_list.html"

    crossref_templates = {
        "form": "admin/bpp/wydawnictwo_zwarte/crossref_pobierz.html",
        "show": "admin/bpp/wydawnictwo_zwarte/crossref_pokaz.html",
    }

    crossref_pbn_templates = {
        "form": "admin/bpp/wydawnictwo_zwarte/crossref_pbn_pobierz.html",
        "show": "admin/bpp/wydawnictwo_zwarte/crossref_pbn_pokaz.html",
    }

    form = Wydawnictwo_ZwarteForm
    djangoql_completion_enabled_by_default = False
    djangoql_completion = True
    search_fields = Wydawnictwo_ZwarteAdmin_Baza.search_fields
    resource_class = resources.Wydawnictwo_ZwarteResource
    bibtex_resource_class = resources.Wydawnictwo_ZwarteBibTeXResource

    inlines = (
        generuj_inline_dla_autorow(Wydawnictwo_Zwarte_Autor),
        NagrodaInline,
        Wydawnictwo_Zwarte_Zewnetrzna_Baza_DanychInline,
        Grant_RekorduInline,
        Element_RepozytoriumInline,
        Wydawnictwo_Zwarte_StreszczenieInline,
    )

    list_filter = Wydawnictwo_ZwarteAdmin_Baza.list_filter + [
        CalkowitaLiczbaAutorowFilter,
        "openaccess_tryb_dostepu",
        "openaccess_wersja_tekstu",
        "openaccess_licencja",
        "openaccess_czas_publikacji",
    ]

    list_select_related = {
        "__always__": ["typ_kbn", "charakter_formalny"],
        "wydawnictwo_nadrzedne": ["wydawnictwo_nadrzedne"],
        "wydawnictwo_nadrzedne_col": ["wydawnictwo_nadrzedne"],
        "wydawca": ["wydawca"],
    }

    autocomplete_fields = [
        "pbn_uid",
    ]

    fieldsets = (
        (
            "Wydawnictwo zwarte",
            {
                "fields": fieldsets.DWA_TYTULY
                + fieldsets.MODEL_ZE_SZCZEGOLAMI
                + (
                    "wydawnictwo_nadrzedne",
                    "wydawnictwo_nadrzedne_w_pbn",
                    "konferencja",
                    "calkowita_liczba_autorow",
                    "calkowita_liczba_redaktorow",
                    "oznaczenie_wydania",
                    "miejsce_i_rok",
                    "wydawca",
                    "wydawca_opis",
                )
                + fieldsets.MODEL_Z_ISBN
                + fieldsets.MODEL_Z_ROKIEM
            },
        ),
        fieldsets.SERIA_WYDAWNICZA_FIELDSET,
        fieldsets.EKSTRA_INFORMACJE_WYDAWNICTWO_ZWARTE_FIELDSET,
        fieldsets.MODEL_TYPOWANY_FIELDSET,
        fieldsets.MODEL_PUNKTOWANY_FIELDSET,
        fieldsets.POZOSTALE_MODELE_WYDAWNICTWO_ZWARTE_FIELDSET,
        fieldsets.ADNOTACJE_Z_DATAMI_ORAZ_PBN_FIELDSET,
        fieldsets.MODEL_OPCJONALNIE_NIE_EKSPORTOWANY_DO_API_FIELDSET,
        fieldsets.OPENACCESS_FIELDSET,
        fieldsets.PRACA_WYBITNA_FIELDSET,
        fieldsets.PRZED_PO_LISCIE_AUTOROW_FIELDSET,
        fieldsets.MODEL_Z_OPLATA_ZA_PUBLIKACJE_FIELDSET,
    )

    def save_model(self, request, obj, form, change):
        poszukaj_duplikatu_pola_www_i_ewentualnie_zmien(request, obj)

        # Wyświetl ostrzeżenia z walidacji ISBN
        if hasattr(form, "_warnings") and form._warnings:
            for warning in form._warnings:
                messages.warning(request, warning)

        super().save_model(request, obj, form, change)
        if (
            obj.rok >= 2017
            and obj.rok <= 2020
            and obj.charakter_formalny.charakter_sloty is None
        ):
            messages.warning(
                request,
                f'Punkty dla dyscyplin dla "{helpers.link_do_obiektu(obj)}" nie będą liczone, gdyż jest to ani książka, ani rozdział',
            )
        else:
            helpers.pbn_api.gui.sprobuj_policzyc_sloty(request, obj)

        sprawdz_duplikaty_www_doi(request, obj)


admin.site.register(Wydawnictwo_Zwarte, Wydawnictwo_ZwarteAdmin)
