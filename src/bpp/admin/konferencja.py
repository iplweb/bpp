from django import forms

from miniblog.admin import SmallerTextarea
from ..models.konferencja import Konferencja
from .core import BaseBppAdminMixin
from .helpers import ADNOTACJE_FIELDSET

from django.contrib import admin

from bpp.admin.helpers import LimitingFormset
from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte


class Wydawnictwo_Zwarte_Konferencja_Form(forms.ModelForm):
    model = Wydawnictwo_Zwarte

    class Meta:
        fields = [
            "tytul_oryginalny",
            "charakter_formalny",
            "typ_kbn",
            "rok",
            "jezyk",
            "status_korekty",
        ]
        widgets = {"tytul_oryginalny": SmallerTextarea}


class Wydawnictwo_Ciagle_Konferencja_Form(forms.ModelForm):
    model = Wydawnictwo_Ciagle

    class Meta:
        fields = [
            "tytul_oryginalny",
            "charakter_formalny",
            "typ_kbn",
            "rok",
            "jezyk",
            "status_korekty",
        ]
        widgets = {"tytul_oryginalny": SmallerTextarea}


class Wydawnictwo_Zwarte_KonferencjaInline(admin.TabularInline):
    form = Wydawnictwo_Zwarte_Konferencja_Form
    model = Wydawnictwo_Zwarte
    formset = LimitingFormset
    extra = 0


class Wydawnictwo_Ciagle_KonferencjaInline(admin.TabularInline):
    form = Wydawnictwo_Ciagle_Konferencja_Form
    model = Wydawnictwo_Ciagle
    formset = LimitingFormset
    extra = 0


class KonferencjaAdmin(BaseBppAdminMixin, admin.ModelAdmin):
    list_display = [
        "nazwa",
        "typ_konferencji",
        "rozpoczecie",
        "zakonczenie",
        "miasto",
        "panstwo",
        "baza_scopus",
        "baza_wos",
        "pbn_uid",
    ]
    list_filter = [
        "miasto",
        "panstwo",
        "rozpoczecie",
        "zakonczenie",
        "baza_scopus",
        "baza_wos",
        "baza_inna",
        "typ_konferencji",
    ]
    search_fields = [
        "nazwa",
        "rozpoczecie",
        "zakonczenie",
        "miasto",
        "panstwo",
        "pbn_uid__pk",
    ]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "nazwa",
                    "skrocona_nazwa",
                    "typ_konferencji",
                    "rozpoczecie",
                    "zakonczenie",
                    "miasto",
                    "panstwo",
                    "baza_scopus",
                    "baza_wos",
                    "baza_inna",
                    "pbn_uid",
                )
            },
        ),
        ADNOTACJE_FIELDSET,
    )
    inlines = [
        Wydawnictwo_Zwarte_KonferencjaInline,
        Wydawnictwo_Ciagle_KonferencjaInline,
    ]

    readonly_fields = ["ostatnio_zmieniony"]

    autocomplete_fields = [
        "pbn_uid",
    ]


admin.site.register(Konferencja, KonferencjaAdmin)
