# -*- encoding: utf-8 -*-

from django.forms.widgets import Textarea
from django.db import models

# Pomocnik dla klasy ModelZMetryczka


class ZapiszZAdnotacjaMixin:
    readonly_fields = ('ostatnio_zmieniony', )

ADNOTACJE_FIELDSET = ('Adnotacje', {
    'classes': ('grp-collapse grp-closed', ),
    'fields': (ZapiszZAdnotacjaMixin.readonly_fields + ('adnotacje',))})

HISTORYCZNY_FIELDSET = ('Historia', {
    'classes': ('grp-collapse grp-closed', ),
    'fields': ('rozpoczecie_funkcjonowania', 'zakonczenie_funkcjonowania')})

DWA_TYTULY = (
    'tytul_oryginalny',
    'tytul',
    )


MODEL_ZE_SZCZEGOLAMI = (
    'informacje',
    'szczegoly',
    'uwagi',
    'slowa_kluczowe',
    )

MODEL_Z_ISSN = (
    'issn',
    'e_issn',
    )

MODEL_Z_ISBN = (
    'isbn',
    'e_isbn',
    )

MODEL_Z_WWW = (
    'www',
    'dostep_dnia'
    )

MODEL_Z_ROKIEM = (
    'rok',
    )

MODEL_TYPOWANY = (
    'jezyk',
    'typ_kbn',
    )

MODEL_PUNKTOWANY = (
    'punkty_kbn',
    'impact_factor',
    'index_copernicus',
    'punktacja_wewnetrzna',
    'weryfikacja_punktacji',
    )

MODEL_PUNKTOWANY_KOMISJA_CENTRALNA = (
    'kc_impact_factor',
    'kc_punkty_kbn',
    'kc_index_copernicus'
)

MODEL_Z_INFORMACJA_Z = (
    'informacja_z',
    )

MODEL_ZE_STATUSEM = (
    'status_korekty',
    )

MODEL_AFILIOWANY_RECENZOWANY = (
    'afiliowana',
    'recenzowana'
    )

MODEL_TYPOWANY_BEZ_CHARAKTERU_FIELDSET = ('Typ', {
    'classes': ('', ),
    'fields': MODEL_TYPOWANY})

MODEL_TYPOWANY_FIELDSET = ('Typ', {
    'classes': ('', ),
    'fields': ('charakter_formalny',) + MODEL_TYPOWANY})

MODEL_PUNKTOWANY_FIELDSET = ('Punktacja', {
    'classes': ('', ),
    'fields': MODEL_PUNKTOWANY})

MODEL_PUNKTOWANY_WYDAWNICTWO_CIAGLE_FIELDSET = ('Punktacja', {
    'classes': ('', ),
    'fields': MODEL_PUNKTOWANY + ('uzupelnij_punktacje', )})

MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET = (
    'Punktacja Komisji Centralnej', {
        'classes': ('grp-collapse grp-closed', ),
        'fields': MODEL_PUNKTOWANY_KOMISJA_CENTRALNA})

POZOSTALE_MODELE_FIELDSET = ('Pozostałe informacje', {
    'classes': ('',),
    'fields': MODEL_Z_INFORMACJA_Z
              + MODEL_ZE_STATUSEM
              + MODEL_AFILIOWANY_RECENZOWANY
})

POZOSTALE_MODELE_WYDAWNICTWO_ZWARTE_FIELDSET = ('Pozostałe informacje', {
    'classes': ('',),
    'fields': ('liczba_znakow_wydawniczych',)
              + MODEL_Z_INFORMACJA_Z
              + MODEL_ZE_STATUSEM
              + MODEL_AFILIOWANY_RECENZOWANY
})


EKSTRA_INFORMACJE_WYDAWNICTWO_CIAGLE_FIELDSET = ('Ekstra informacje', {
    'classes': ('grp-collapse grp-closed', ),
    'fields': MODEL_Z_ISSN + MODEL_Z_WWW
})

EKSTRA_INFORMACJE_WYDAWNICTWO_ZWARTE_FIELDSET = ('Ekstra informacje', {
    'classes': ('grp-collapse grp-closed', ),
    'fields': MODEL_Z_ISBN + MODEL_Z_WWW
})


def js_openwin(url, handle, options):
    options = ",".join(["%s=%s" % (a, b) for a, b in options.items()])
    d = dict(url=url, handle=handle, options=options)
    return "window.open(\'%(url)s\','\%(handle)s\',\'%(options)s\')" % d

NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW = {
    models.TextField: {
        'widget': Textarea(attrs={'rows':2, 'cols': 90, 'class': 'charmap'})},
    }

