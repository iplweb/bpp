# -*- encoding: utf-8 -*-

from django import forms
from django.db import models
from django.forms import BaseInlineFormSet
from django.forms.widgets import Textarea

from bpp.models import Status_Korekty

CHARMAP_SINGLE_LINE = forms.TextInput(
    attrs={'class': 'charmap', 'style': "width: 500px"})


# Pomocnik dla klasy ModelZMetryczka


class ZapiszZAdnotacjaMixin:
    readonly_fields = ('ostatnio_zmieniony',)


class AdnotacjeZDatamiMixin:
    readonly_fields = ('utworzono', 'ostatnio_zmieniony', 'id')


class AdnotacjeZDatamiOrazPBNMixin:
    readonly_fields = (
        'utworzono',
        'ostatnio_zmieniony',
        'ostatnio_zmieniony_dla_pbn',
        'id',
        'pbn_id')


ADNOTACJE_FIELDSET = ('Adnotacje', {
    'classes': ('grp-collapse grp-closed',),
    'fields': (ZapiszZAdnotacjaMixin.readonly_fields + ('adnotacje',))})

ADNOTACJE_Z_DATAMI_FIELDSET = ('Adnotacje', {
    'classes': ('grp-collapse grp-closed',),
    'fields': AdnotacjeZDatamiMixin.readonly_fields + ('adnotacje',)
})

ADNOTACJE_Z_DATAMI_ORAZ_PBN_FIELDSET = ('Adnotacje', {
    'classes': ('grp-collapse grp-closed',),
    'fields': AdnotacjeZDatamiOrazPBNMixin.readonly_fields + ('adnotacje',)
})

OPENACCESS_FIELDSET = ("OpenAccess", {
    'classes': ('grp-collapse grp-closed',),
    'fields': ('openaccess_tryb_dostepu', 'openaccess_licencja',
               'openaccess_wersja_tekstu', 'openaccess_czas_publikacji',
               'openaccess_ilosc_miesiecy')
})

DWA_TYTULY = (
    'tytul_oryginalny',
    'tytul',
)

MODEL_ZE_SZCZEGOLAMI = (
    'informacje',
    'szczegoly',
    'uwagi',
    'slowa_kluczowe',
    'strony',
    'tom'
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
    'dostep_dnia',
    'public_www',
    'public_dostep_dnia',
)

MODEL_Z_PUBMEDID = (
    'pubmed_id',
)

MODEL_Z_DOI = (
    'doi',
)

MODEL_Z_LICZBA_CYTOWAN = (
    'liczba_cytowan',
)

MODEL_Z_ROKIEM = (
    'rok',
)

MODEL_TYPOWANY = (
    'jezyk',
    'typ_kbn',
)

MODEL_PUNKTOWANY_BAZA = (
    'punkty_kbn',
    'impact_factor',
    'index_copernicus',
    'punktacja_snip',
    'punktacja_wewnetrzna',
)

MODEL_PUNKTOWANY = MODEL_PUNKTOWANY_BAZA + (
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

MODEL_Z_LICZBA_ZNAKOW_WYDAWNICZYCH = (
    'liczba_znakow_wydawniczych',
)

MODEL_ZE_STATUSEM = (
    'status_korekty',
)

MODEL_RECENZOWANY = (
    'recenzowana',
)

MODEL_TYPOWANY_BEZ_CHARAKTERU_FIELDSET = ('Typ', {
    'classes': ('',),
    'fields': MODEL_TYPOWANY})

MODEL_TYPOWANY_FIELDSET = ('Typ', {
    'classes': ('',),
    'fields': ('charakter_formalny',) + MODEL_TYPOWANY})

MODEL_PUNKTOWANY_FIELDSET = ('Punktacja', {
    'classes': ('',),
    'fields': MODEL_PUNKTOWANY})

MODEL_PUNKTOWANY_WYDAWNICTWO_CIAGLE_FIELDSET = ('Punktacja', {
    'classes': ('',),
    'fields': MODEL_PUNKTOWANY + ('uzupelnij_punktacje',)})

MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET = (
    'Punktacja Komisji Centralnej', {
        'classes': ('grp-collapse grp-closed',),
        'fields': MODEL_PUNKTOWANY_KOMISJA_CENTRALNA})

POZOSTALE_MODELE_FIELDSET = ('Pozostałe informacje', {
    'classes': ('',),
    'fields': MODEL_Z_INFORMACJA_Z
              + MODEL_ZE_STATUSEM
              + MODEL_RECENZOWANY
})

POZOSTALE_MODELE_WYDAWNICTWO_CIAGLE_FIELDSET = ('Pozostałe informacje', {
    'classes': ('',),
    'fields': MODEL_Z_LICZBA_ZNAKOW_WYDAWNICZYCH
              + MODEL_Z_INFORMACJA_Z
              + MODEL_ZE_STATUSEM
              + MODEL_RECENZOWANY
})

POZOSTALE_MODELE_WYDAWNICTWO_ZWARTE_FIELDSET = ('Pozostałe informacje', {
    'classes': ('',),
    'fields': MODEL_Z_LICZBA_ZNAKOW_WYDAWNICZYCH
              + MODEL_Z_INFORMACJA_Z
              + MODEL_ZE_STATUSEM
              + MODEL_RECENZOWANY
})

SERIA_WYDAWNICZA_FIELDSET = ('Seria wydawnicza', {
    'classes': ('grp-collapse grp-closed',),
    'fields': (
        'seria_wydawnicza',
        'numer_w_serii')
})

PRACA_WYBITNA_FIELDSET = ('Praca wybitna', {
    'classes': ('grp-collapse grp-closed',),
    'fields': (
        'praca_wybitna',
        'uzasadnienie_wybitnosci')
})

EKSTRA_INFORMACJE_WYDAWNICTWO_CIAGLE_FIELDSET = ('Ekstra informacje', {
    'classes': ('grp-collapse grp-closed',),
    'fields': MODEL_Z_ISSN + MODEL_Z_WWW + MODEL_Z_PUBMEDID + MODEL_Z_DOI + MODEL_Z_LICZBA_CYTOWAN
})

EKSTRA_INFORMACJE_WYDAWNICTWO_ZWARTE_FIELDSET = ('Ekstra informacje', {
    'classes': ('grp-collapse grp-closed',),
    'fields': MODEL_Z_ISSN +
              MODEL_Z_WWW +
              MODEL_Z_PUBMEDID +
              MODEL_Z_DOI +
              MODEL_Z_LICZBA_CYTOWAN
})

EKSTRA_INFORMACJE_DOKTORSKA_HABILITACYJNA_FIELDSET = ('Ekstra informacje', {
    'classes': ('grp-collapse grp-closed',),
    'fields': MODEL_Z_WWW +
              MODEL_Z_PUBMEDID +
              MODEL_Z_DOI +
              MODEL_Z_LICZBA_CYTOWAN
})


def js_openwin(url, handle, options):
    options = ",".join(["%s=%s" % (a, b) for a, b in list(options.items())])
    d = dict(url=url, handle=handle, options=options)
    return "window.open(\'%(url)s\','\%(handle)s\',\'%(options)s\')" % d


NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW = {
    models.TextField: {
        'widget': Textarea(attrs={'rows': 2, 'cols': 90, 'class': 'charmap'})},
}


class DomyslnyStatusKorektyMixin:
    status_korekty = forms.ModelChoiceField(
        required=True,
        queryset=Status_Korekty.objects.all(),
        initial=lambda: Status_Korekty.objects.first()
    )


class Wycinaj_W_z_InformacjiMixin:
    def clean_informacje(self):
        i = self.cleaned_data.get("informacje")
        if i:
            l = i.lower()
            n = 0
            if l.startswith("w:"):
                n = 2
            if l.startswith("w :"):
                n = 3
            if n:
                return i[n:].strip()
        return i


class LimitingFormset(BaseInlineFormSet):
    def get_queryset(self):
        if not hasattr(self, '_queryset_limited'):
            qs = super(LimitingFormset, self).get_queryset()
            self._queryset_limited = qs[:100]
        return self._queryset_limited
