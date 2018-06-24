# -*- encoding: utf-8 -*-

from django.contrib import admin

from .core import CommitedModelAdmin
from .helpers import ADNOTACJE_FIELDSET
from ..models.konferencja import Konferencja


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

    readonly_fields = ['ostatnio_zmieniony']
    pass

admin.site.register(Konferencja, KonferencjaAdmin)
