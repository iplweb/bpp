from dal import autocomplete
from django import forms
from django.forms.utils import flatatt
from djangoql.admin import DjangoQLSearchMixin
from mptt.forms import TreeNodeChoiceField
from taggit.forms import TextareaTagWidget

from crossref_bpp.mixins import AdminCrossrefAPIMixin
from dynamic_columns.mixins import DynamicColumnsMixin
from pbn_api.models import Publication
from . import BaseBppAdminMixin
from .actions import (
    ustaw_po_korekcie,
    ustaw_przed_korekta,
    ustaw_w_trakcie_korekty,
    wyslij_do_pbn,
)
from .core import KolumnyZeSkrotamiMixin, generuj_inline_dla_autorow
from .crossref_api_helpers import (
    KorzystaZCrossRefAPIStreszczenieInlineMixin,
    UzupelniajWstepneDanePoCrossRefAPIMixin,
)

# Widget do automatycznego uzupełniania punktacji wydawnictwa ciągłego
from .element_repozytorium import Element_RepozytoriumInline
from .grant import Grant_RekorduInline
from .helpers import (
    MODEL_OPCJONALNIE_NIE_EKSPORTOWANY_DO_API_FIELDSET,
    MODEL_Z_OPLATA_ZA_PUBLIKACJE_FIELDSET,
    OptionalPBNSaveMixin,
    sprawdz_duplikaty_www_doi,
)
from .util import CustomizableFormsetParamsAdminMixinWyrzucWDjango40
from .xlsx_export import resources
from .xlsx_export.mixins import EksportDanychMixin
from .zglos_publikacje_helpers import UzupelniajWstepneDanePoNumerzeZgloszeniaMixin

from django.contrib import admin

from django.utils.safestring import mark_safe

from bpp.admin.filters import (
    DOIUstawioneFilter,
    LiczbaZnakowFilter,
    OstatnioZmienionePrzezFilter,
    PBN_UID_IDObecnyFilter,
    UtworzonePrzezFilter,
)
from bpp.admin.helpers import (
    ADNOTACJE_Z_DATAMI_ORAZ_PBN_FIELDSET,
    DWA_TYTULY,
    EKSTRA_INFORMACJE_WYDAWNICTWO_CIAGLE_FIELDSET,
    MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET,
    MODEL_PUNKTOWANY_WYDAWNICTWO_CIAGLE_FIELDSET,
    MODEL_TYPOWANY_FIELDSET,
    MODEL_Z_ROKIEM,
    MODEL_ZE_SZCZEGOLAMI,
    NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW,
    OPENACCESS_FIELDSET,
    POZOSTALE_MODELE_WYDAWNICTWO_CIAGLE_FIELDSET,
    PRACA_WYBITNA_FIELDSET,
    PRZED_PO_LISCIE_AUTOROW_FIELDSET,
    AdnotacjeZDatamiOrazPBNMixin,
    DomyslnyStatusKorektyMixin,
    sprobuj_policzyc_sloty,
)
from bpp.admin.nagroda import NagrodaInline
from bpp.models import (  # Publikacja_Habilitacyjna
    Charakter_Formalny,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Streszczenie,
    Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych,
    Zrodlo,
    nie_zawiera_adresu_doi_org,
    nie_zawiera_http_https,
)

# Proste tabele
from bpp.models.konferencja import Konferencja
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor

#
# Wydaniwcto Ciągłe
#


class Button(forms.Widget):
    """
    A widget that handles a submit button.
    """

    def render(self, name, value, attrs=None, renderer=None):
        final_attrs = self.build_attrs(self.attrs, dict(type="button", name=name))

        return mark_safe(
            '<input type="button"%s value="%s" />'
            % (
                flatatt(final_attrs),
                final_attrs["label"],
            )
        )


class CleanDOIWWWPublicWWWMixin:
    def clean_www(self):
        v = self.cleaned_data.get("www")
        nie_zawiera_adresu_doi_org(v)
        return v

    def clean_public_www(self):
        v = self.cleaned_data.get("public_www")
        nie_zawiera_adresu_doi_org(v)
        return v

    def clean_doi(self):
        v = self.cleaned_data.get("doi")
        nie_zawiera_http_https(v)
        return v


class Wydawnictwo_CiagleForm(CleanDOIWWWPublicWWWMixin, forms.ModelForm):
    zrodlo = forms.ModelChoiceField(
        queryset=Zrodlo.objects.all(),
        widget=autocomplete.ModelSelect2(url="bpp:admin-zrodlo-autocomplete"),
    )

    uzupelnij_punktacje = forms.CharField(
        initial=None,
        max_length=50,
        required=False,
        label="Uzupełnij punktację",
        widget=Button(
            dict(
                id="id_uzupelnij_punktacje",
                label="Uzupełnij punktację",
            )
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
            url="bpp:publication-autocomplete", attrs=dict(style="width: 746px;")
        ),
    )

    charakter_formalny = TreeNodeChoiceField(
        required=True, queryset=Charakter_Formalny.objects.all()
    )

    status_korekty = DomyslnyStatusKorektyMixin.status_korekty

    class Meta:
        fields = "__all__"

        widgets = {
            "strony": forms.TextInput(attrs=dict(style="width: 150px")),
            "tom": forms.TextInput(attrs=dict(style="width: 150px")),
            "nr_zeszytu": forms.TextInput(attrs=dict(style="width: 150px")),
            "slowa_kluczowe": TextareaTagWidget(attrs={"rows": 2}),
        }


class Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychForm(forms.ModelForm):
    class Meta:
        fields = ["baza", "info"]


class Wydawnictwo_Ciagle_StreszczenieInline(
    KorzystaZCrossRefAPIStreszczenieInlineMixin, admin.StackedInline
):
    model = Wydawnictwo_Ciagle_Streszczenie
    extra = 0
    fields = ["jezyk_streszczenia", "streszczenie"]


class Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychInline(admin.StackedInline):
    model = Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych
    extra = 0
    form = Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychForm


class Wydawnictwo_CiagleAdmin(
    DjangoQLSearchMixin,
    OptionalPBNSaveMixin,
    KolumnyZeSkrotamiMixin,
    AdnotacjeZDatamiOrazPBNMixin,
    BaseBppAdminMixin,
    UzupelniajWstepneDanePoNumerzeZgloszeniaMixin,
    UzupelniajWstepneDanePoCrossRefAPIMixin,
    CustomizableFormsetParamsAdminMixinWyrzucWDjango40,
    AdminCrossrefAPIMixin,
    EksportDanychMixin,
    DynamicColumnsMixin,
    admin.ModelAdmin,
):
    change_list_template = "admin/bpp/wydawnictwo_ciagle/change_list.html"

    crossref_templates = {
        "form": "admin/bpp/wydawnictwo_ciagle/crossref_pobierz.html",
        "show": "admin/bpp/wydawnictwo_ciagle/crossref_pokaz.html",
    }

    resource_class = resources.Wydawnictwo_CiagleResource

    djangoql_completion_enabled_by_default = False
    djangoql_completion = True

    formfield_overrides = NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW
    actions = [
        ustaw_po_korekcie,
        ustaw_w_trakcie_korekty,
        ustaw_przed_korekta,
        wyslij_do_pbn,
    ]

    form = Wydawnictwo_CiagleForm

    ordering = ("-ostatnio_zmieniony",)

    list_display_always = ["tytul_oryginalny"]

    list_display_default = [
        "zrodlo_col",
        "rok",
        "typ_kbn__skrot",
        "charakter_formalny__skrot",
        "liczba_znakow_wydawniczych",
        "ostatnio_zmieniony",
    ]

    list_display_allowed = "__all__"

    list_select_related = {
        "__always__": ["typ_kbn", "charakter_formalny"],
        "zrodlo_col": ["zrodlo"],
    }

    search_fields = [
        "tytul",
        "tytul_oryginalny",
        "szczegoly",
        "uwagi",
        "informacje",
        "slowa_kluczowe__name",
        "rok",
        "id",
        "issn",
        "e_issn",
        "zrodlo__nazwa",
        "zrodlo__skrot",
        "adnotacje",
        "liczba_znakow_wydawniczych",
        "konferencja__nazwa",
        "doi",
        "pbn_uid__pk",
    ]

    list_filter = [
        "status_korekty",
        "recenzowana",
        "typ_kbn",
        "charakter_formalny",
        "jezyk",
        LiczbaZnakowFilter,
        "rok",
        DOIUstawioneFilter,
        "openaccess_tryb_dostepu",
        "openaccess_wersja_tekstu",
        "openaccess_licencja",
        "openaccess_czas_publikacji",
        OstatnioZmienionePrzezFilter,
        UtworzonePrzezFilter,
        PBN_UID_IDObecnyFilter,
    ]

    autocomplete_fields = [
        "pbn_uid",
    ]

    fieldsets = (
        (
            "Wydawnictwo ciągłe",
            {
                "fields": DWA_TYTULY
                + (
                    "zrodlo",
                    "konferencja",
                )
                + MODEL_ZE_SZCZEGOLAMI
                + ("nr_zeszytu",)
                + MODEL_Z_ROKIEM
            },
        ),
        EKSTRA_INFORMACJE_WYDAWNICTWO_CIAGLE_FIELDSET,
        MODEL_TYPOWANY_FIELDSET,
        MODEL_PUNKTOWANY_WYDAWNICTWO_CIAGLE_FIELDSET,
        MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET,
        POZOSTALE_MODELE_WYDAWNICTWO_CIAGLE_FIELDSET,
        ADNOTACJE_Z_DATAMI_ORAZ_PBN_FIELDSET,
        MODEL_OPCJONALNIE_NIE_EKSPORTOWANY_DO_API_FIELDSET,
        OPENACCESS_FIELDSET,
        PRACA_WYBITNA_FIELDSET,
        PRZED_PO_LISCIE_AUTOROW_FIELDSET,
        MODEL_Z_OPLATA_ZA_PUBLIKACJE_FIELDSET,
    )

    inlines = (
        generuj_inline_dla_autorow(Wydawnictwo_Ciagle_Autor),
        NagrodaInline,
        Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychInline,
        Grant_RekorduInline,
        Element_RepozytoriumInline,
        Wydawnictwo_Ciagle_StreszczenieInline,
    )

    def zrodlo_col(self, obj):
        if obj.zrodlo:
            try:
                return obj.zrodlo.nazwa
            except Zrodlo.DoesNotExist:
                return ""

    zrodlo_col.admin_order_field = "zrodlo__nazwa"
    zrodlo_col.short_description = "Źródło"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        sprobuj_policzyc_sloty(request, obj)
        sprawdz_duplikaty_www_doi(request, obj)


admin.site.register(Wydawnictwo_Ciagle, Wydawnictwo_CiagleAdmin)
