# -*- encoding: utf-8 -*-

from django.contrib import admin

from bpp.admin.helpers import ADNOTACJE_FIELDSET
from bpp.models.konferencja import Konferencja

from .common import CommitedModelAdmin

class KonferencjaAdmin(CommitedModelAdmin):
    list_display = ['nazwa', 'rozpoczecie', 'zakonczenie', 'miasto',
                    'panstwo', 'baza_scopus', 'baza_wos']
    list_filter = ['miasto', 'panstwo', 'rozpoczecie', 'zakonczenie',
                   'baza_scopus', 'baza_wos', 'baza_inna']
    search_fields = ['nazwa', 'rozpoczecie', 'zakonczenie', 'miasto',
                     'panstwo']
    fieldsets = (
        (None, {
            'fields': (
                'nazwa',
                'skrocona_nazwa',
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