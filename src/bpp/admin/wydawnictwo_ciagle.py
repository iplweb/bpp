# -*- encoding: utf-8 -*-

from dal import autocomplete
from django import forms
from django.forms.utils import flatatt
from mptt.forms import TreeNodeChoiceField
from .core import CommitedModelAdmin, KolumnyZeSkrotamiMixin, generuj_inline_dla_autorow

# Widget do automatycznego uzupełniania punktacji wydawnictwa ciągłego
from .element_repozytorium import Element_RepozytoriumInline
from .grant import Grant_RekorduInline
from .helpers import MODEL_OPCJONALNIE_NIE_EKSPORTOWANY_DO_API_FIELDSET

from django.contrib import admin

from django.utils.safestring import mark_safe

from bpp.admin.filters import DOIUstawioneFilter, LiczbaZnakowFilter
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
    Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych,
    Zrodlo,
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


class Wydawnictwo_CiagleForm(forms.ModelForm):
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
        }


class Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychForm(forms.ModelForm):
    class Meta:
        fields = ["baza", "info"]


class Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychInline(admin.StackedInline):
    model = Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych
    extra = 0
    form = Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychForm


class Wydawnictwo_CiagleAdmin(
    KolumnyZeSkrotamiMixin, AdnotacjeZDatamiOrazPBNMixin, CommitedModelAdmin
):
    formfield_overrides = NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW

    form = Wydawnictwo_CiagleForm

    list_display = [
        "tytul_oryginalny",
        "zrodlo_col",
        "rok",
        "typ_kbn__skrot",
        "charakter_formalny__skrot",
        "liczba_znakow_wydawniczych",
        "ostatnio_zmieniony",
    ]

    list_select_related = ["zrodlo", "typ_kbn", "charakter_formalny"]

    search_fields = [
        "tytul",
        "tytul_oryginalny",
        "szczegoly",
        "uwagi",
        "informacje",
        "slowa_kluczowe",
        "rok",
        "id",
        "issn",
        "e_issn",
        "zrodlo__nazwa",
        "zrodlo__skrot",
        "adnotacje",
        "liczba_znakow_wydawniczych",
        "konferencja__nazwa",
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
    )

    inlines = (
        generuj_inline_dla_autorow(Wydawnictwo_Ciagle_Autor),
        NagrodaInline,
        Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychInline,
        Grant_RekorduInline,
        Element_RepozytoriumInline,
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
        super(Wydawnictwo_CiagleAdmin, self).save_model(request, obj, form, change)
        sprobuj_policzyc_sloty(request, obj)


admin.site.register(Wydawnictwo_Ciagle, Wydawnictwo_CiagleAdmin)
