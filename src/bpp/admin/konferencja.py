# -*- encoding: utf-8 -*-

from django import forms
from django.contrib import admin

from bpp.admin import LimitingFormset
from bpp.models import Wydawnictwo_Zwarte, Wydawnictwo_Ciagle
from miniblog.admin import SmallerTextarea
from .core import CommitedModelAdmin
from .helpers import ADNOTACJE_FIELDSET
from ..models.konferencja import Konferencja


class Wydawnictwo_Zwarte_Konferencja_Form(forms.ModelForm):
    model = Wydawnictwo_Zwarte

    class Meta:
        fields = ['tytul_oryginalny', 'charakter_formalny', "typ_kbn", "rok", "jezyk", "status_korekty"]
        widgets = {'tytul_oryginalny': SmallerTextarea}


class Wydawnictwo_Ciagle_Konferencja_Form(forms.ModelForm):
    model = Wydawnictwo_Ciagle

    class Meta:
        fields = ['tytul_oryginalny', 'charakter_formalny', "typ_kbn", "rok", "jezyk", "status_korekty"]
        widgets = {'tytul_oryginalny': SmallerTextarea}


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


class KonferencjaAdmin(CommitedModelAdmin):
    list_display = ['nazwa', 'typ_konferencji', 'rozpoczecie', 'zakonczenie', 'miasto',
                    'panstwo', 'baza_scopus', 'baza_wos']
    list_filter = ['miasto', 'panstwo', 'rozpoczecie', 'zakonczenie',
                   'baza_scopus', 'baza_wos', 'baza_inna', 'typ_konferencji']
    search_fields = ['nazwa', 'rozpoczecie', 'zakonczenie', 'miasto',
                     'panstwo']
    fieldsets = (
        (None, {
            'fields': (
                'nazwa',
                'skrocona_nazwa',
                'typ_konferencji',
                'rozpoczecie',
                'zakonczenie',
                'miasto',
                'panstwo',
                'baza_scopus',
                'baza_wos',
                'baza_inna')
        }),
        ADNOTACJE_FIELDSET
    )
    inlines = [
        Wydawnictwo_Zwarte_KonferencjaInline,
        Wydawnictwo_Ciagle_KonferencjaInline
    ]

    readonly_fields = ['ostatnio_zmieniony']
    pass


admin.site.register(Konferencja, KonferencjaAdmin)
