from dal import autocomplete
from django import forms
from django.contrib import admin
from taggit.forms import TextareaTagWidget

from bpp.admin.helpers.widgets import (
    COMMA_DECIMAL_FIELD_OVERRIDE,
    NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW,
)

from ..models import Autor, Jednostka, Praca_Doktorska
from .actions import ustaw_po_korekcie, ustaw_przed_korekta, ustaw_w_trakcie_korekty
from .core import BaseBppAdminMixin
from .element_repozytorium import Element_RepozytoriumInline
from .filters import OstatnioZmienionePrzezFilter, UtworzonePrzezFilter
from .grant import Grant_RekorduInline
from .helpers.constance_field_mixin import ConstanceScoringFieldsMixin
from .helpers.fieldsets import (
    ADNOTACJE_Z_DATAMI_FIELDSET,
    DWA_TYTULY,
    EKSTRA_INFORMACJE_DOKTORSKA_HABILITACYJNA_FIELDSET,
    MODEL_OPCJONALNIE_NIE_EKSPORTOWANY_DO_API_FIELDSET,
    MODEL_PUNKTOWANY_FIELDSET,
    MODEL_TYPOWANY_BEZ_CHARAKTERU_FIELDSET,
    MODEL_Z_ISBN,
    MODEL_Z_OPLATA_ZA_PUBLIKACJE_FIELDSET,
    MODEL_Z_ROKIEM,
    MODEL_ZE_SZCZEGOLAMI,
    POZOSTALE_MODELE_FIELDSET,
    AdnotacjeZDatamiMixin,
)
from .helpers.mixins import DomyslnyStatusKorektyMixin, Wycinaj_W_z_InformacjiMixin
from .wydawnictwo_ciagle import CleanDOIWWWPublicWWWMixin
from .xlsx_export import resources
from .xlsx_export.mixins import EksportDanychZFormatowanieMixin, ExportActionsMixin

# Proste tabele


DOKTORSKA_FIELDS = (
    DWA_TYTULY
    + MODEL_ZE_SZCZEGOLAMI
    + (
        "oznaczenie_wydania",
        "miejsce_i_rok",
        "wydawca",
        "wydawca_opis",
        "autor",
        "jednostka",
        "promotor",
    )
    + MODEL_Z_ISBN
    + MODEL_Z_ROKIEM
)


class Praca_Doktorska_Habilitacyjna_Admin_Base(
    AdnotacjeZDatamiMixin, BaseBppAdminMixin, admin.ModelAdmin
):
    formfield_overrides = {
        **NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW,
        **COMMA_DECIMAL_FIELD_OVERRIDE,
    }
    actions = [ustaw_po_korekcie, ustaw_w_trakcie_korekty, ustaw_przed_korekta]

    list_display = [
        "tytul_oryginalny",
        "autor",
        "jednostka",
        "wydawca",
        "wydawca_opis",
        "typ_kbn",
        "ostatnio_zmieniony",
    ]
    list_select_related = [
        "autor",
        "autor__tytul",
        "jednostka",
        "wydawca",
        "jednostka__wydzial",
        "typ_kbn",
    ]

    search_fields = [
        "tytul",
        "tytul_oryginalny",
        "szczegoly",
        "uwagi",
        "informacje",
        "slowa_kluczowe__name",
        "rok",
        "www",
        "wydawca_opis",
        "wydawca__nazwa",
        "redakcja",
        "autor__tytul__nazwa",
        "jednostka__nazwa",
        "adnotacje",
        "id",
        "doi",
        "pbn_uid__pk",
    ]

    list_filter = [
        "status_korekty",
        "recenzowana",
        "typ_kbn",
        OstatnioZmienionePrzezFilter,
        UtworzonePrzezFilter,
    ]


class Praca_DoktorskaForm(
    Wycinaj_W_z_InformacjiMixin, CleanDOIWWWPublicWWWMixin, forms.ModelForm
):
    autor = forms.ModelChoiceField(
        queryset=Autor.objects.all(),
        widget=autocomplete.ModelSelect2(url="bpp:autor-z-uczelni-autocomplete"),
    )

    jednostka = forms.ModelChoiceField(
        queryset=Jednostka.objects.all(),
        widget=autocomplete.ModelSelect2(url="bpp:jednostka-autocomplete"),
    )

    promotor = forms.ModelChoiceField(
        queryset=Autor.objects.all(),
        widget=autocomplete.ModelSelect2(url="bpp:autor-z-uczelni-autocomplete"),
    )

    status_korekty = DomyslnyStatusKorektyMixin.status_korekty

    class Meta:
        model = Praca_Doktorska
        fields = [
            "tytul_oryginalny",
            "tytul",
            "informacje",
            "szczegoly",
            "uwagi",
            "slowa_kluczowe",
            "slowa_kluczowe_eng",
            "strony",
            "tom",
            "oznaczenie_wydania",
            "miejsce_i_rok",
            "wydawca",
            "wydawca_opis",
            "autor",
            "jednostka",
            "promotor",
            "isbn",
            "e_isbn",
            "rok",
            "www",
            "dostep_dnia",
            "public_www",
            "public_dostep_dnia",
            "pubmed_id",
            "pmc_id",
            "doi",
            "liczba_cytowan",
            "numer_odbitki",
            "jezyk",
            "jezyk_alt",
            "jezyk_orig",
            "typ_kbn",
            "punkty_kbn",
            "impact_factor",
            "index_copernicus",
            "punktacja_snip",
            "punktacja_wewnetrzna",
            "weryfikacja_punktacji",
            "informacja_z",
            "status_korekty",
            "recenzowana",
            "adnotacje",
            "nie_eksportuj_przez_api",
            "opl_pub_cost_free",
            "opl_pub_research_potential",
            "opl_pub_research_or_development_projects",
            "opl_pub_other",
            "opl_pub_amount",
        ]
        widgets = {
            "slowa_kluczowe": TextareaTagWidget(attrs={"rows": 2}),
        }


class Praca_DoktorskaResource(resources.Wydawnictwo_ResourceBase):
    class Meta:
        model = Praca_Doktorska
        exclude = resources.WYDAWNICTWO_TYPOWE_EXCLUDES
        export_order = resources.WYDAWNICTWO_TYPOWY_EXPORT_ORDER


class Praca_DoktorskaAdmin(
    ConstanceScoringFieldsMixin,
    EksportDanychZFormatowanieMixin,
    ExportActionsMixin,
    Praca_Doktorska_Habilitacyjna_Admin_Base,
):
    resource_class = Praca_DoktorskaResource
    bibtex_resource_class = resources.Praca_DoktorskaBibTeXResource

    form = Praca_DoktorskaForm

    fieldsets = (
        ("Praca doktorska", {"fields": DOKTORSKA_FIELDS}),
        EKSTRA_INFORMACJE_DOKTORSKA_HABILITACYJNA_FIELDSET,
        MODEL_TYPOWANY_BEZ_CHARAKTERU_FIELDSET,
        MODEL_PUNKTOWANY_FIELDSET,
        POZOSTALE_MODELE_FIELDSET,
        ADNOTACJE_Z_DATAMI_FIELDSET,
        MODEL_OPCJONALNIE_NIE_EKSPORTOWANY_DO_API_FIELDSET,
        MODEL_Z_OPLATA_ZA_PUBLIKACJE_FIELDSET,
    )

    inlines = (
        Grant_RekorduInline,
        Element_RepozytoriumInline,
    )


admin.site.register(Praca_Doktorska, Praca_DoktorskaAdmin)
