from django import forms
from taggit.forms import TextareaTagWidget

from .core import generuj_inline_dla_autorow
from .element_repozytorium import Element_RepozytoriumInline
from .filters import OstatnioZmienionePrzezFilter, UtworzonePrzezFilter
from .grant import Grant_RekorduInline
from .helpers.fieldsets import (
    ADNOTACJE_Z_DATAMI_FIELDSET,
    MODEL_OPCJONALNIE_NIE_EKSPORTOWANY_DO_API_FIELDSET,
    MODEL_PUNKTOWANY_FIELDSET,
    MODEL_Z_ROKIEM,
    MODEL_Z_WWW,
    MODEL_ZE_SZCZEGOLAMI,
    POZOSTALE_MODELE_FIELDSET,
    AdnotacjeZDatamiMixin,
)
from .helpers.mixins import DomyslnyStatusKorektyMixin, Wycinaj_W_z_InformacjiMixin
from .wydawnictwo_zwarte import Wydawnictwo_ZwarteAdmin_Baza
from .xlsx_export import resources
from .xlsx_export.mixins import EksportDanychZFormatowanieMixin, ExportActionsMixin

from django.contrib import admin

from bpp.models.patent import Patent, Patent_Autor


class Patent_Form(Wycinaj_W_z_InformacjiMixin, forms.ModelForm):
    status_korekty = DomyslnyStatusKorektyMixin.status_korekty

    class Meta:
        fields = "__all__"

        widgets = {
            "slowa_kluczowe": TextareaTagWidget(attrs={"rows": 2}),
        }


class PatentResource(resources.Wydawnictwo_ResourceBase):
    class Meta:
        model = Patent
        exclude = resources.WYDAWNICTWO_TYPOWE_EXCLUDES
        export_order = resources.WYDAWNICTWO_TYPOWY_EXPORT_ORDER


class Patent_Admin(
    AdnotacjeZDatamiMixin,
    EksportDanychZFormatowanieMixin,
    ExportActionsMixin,
    Wydawnictwo_ZwarteAdmin_Baza,
):
    resource_class = PatentResource
    bibtex_resource_class = resources.PatentBibTeXResource

    inlines = (
        generuj_inline_dla_autorow(Patent_Autor),
        Grant_RekorduInline,
        Element_RepozytoriumInline,
    )

    list_display = ["tytul_oryginalny", "ostatnio_zmieniony"]

    search_fields = [
        "tytul_oryginalny",
        "szczegoly",
        "uwagi",
        "informacje",
        "slowa_kluczowe__name",
        "rok",
        "adnotacje",
        "id",
    ]

    list_filter = [
        "status_korekty",
        "recenzowana",
        OstatnioZmienionePrzezFilter,
        UtworzonePrzezFilter,
    ]

    form = Patent_Form

    fieldsets = (
        (
            "Patent",
            {
                "fields": ("tytul_oryginalny",)
                + MODEL_ZE_SZCZEGOLAMI
                + (
                    "wydzial",
                    "rodzaj_prawa",
                    "data_zgloszenia",
                    "numer_zgloszenia",
                    "data_decyzji",
                    "numer_prawa_wylacznego",
                    "wdrozenie",
                )
                + MODEL_Z_ROKIEM
                + MODEL_Z_WWW
            },
        ),
        MODEL_PUNKTOWANY_FIELDSET,
        POZOSTALE_MODELE_FIELDSET,
        ADNOTACJE_Z_DATAMI_FIELDSET,
        MODEL_OPCJONALNIE_NIE_EKSPORTOWANY_DO_API_FIELDSET,
    )


admin.site.register(Patent, Patent_Admin)
