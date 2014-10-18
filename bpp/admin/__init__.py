# -*- encoding: utf-8 -*-
from django.contrib.admin.options import BaseModelAdmin
from django.contrib.contenttypes.admin import GenericTabularInline, \
    GenericInlineModelAdmin
from django.contrib.contenttypes.forms import generic_inlineformset_factory

from bpp import autocomplete_light_registry

from django import forms
from django.utils.safestring import mark_safe
from django import forms
from django.db import transaction
from django.contrib import admin
import autocomplete_light

from bpp.admin.helpers import *

from bpp.models import Jezyk, Typ_KBN, Uczelnia, Wydzial, \
    Jednostka, Tytul, Autor, Autor_Jednostka, Funkcja_Autora, Rodzaj_Zrodla, \
    Zrodlo, Punktacja_Zrodla, Typ_Odpowiedzialnosci, Status_Korekty, \
    Zrodlo_Informacji, Wydawnictwo_Ciagle, Charakter_Formalny, \
    Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor, Praca_Doktorska, \
    Praca_Habilitacyjna, Patent, Patent_Autor, BppUser, Publikacja_Habilitacyjna

# Proste tabele
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor
from bpp.models.zrodlo import Redakcja_Zrodla


class BaseBppAdmin(admin.ModelAdmin):
    pass


admin.site.register(Jezyk, BaseBppAdmin)
admin.site.register(Funkcja_Autora, BaseBppAdmin)
admin.site.register(Rodzaj_Zrodla, BaseBppAdmin)
admin.site.register(Status_Korekty, BaseBppAdmin)
admin.site.register(Zrodlo_Informacji, BaseBppAdmin)


class CommitedModelAdmin(BaseBppAdmin):
    """Ta klasa jest potrzebna, (XXXżeby działały sygnały post_commit.XXX)

    Ta klasa KIEDYŚ była potrzebna, obecnie niespecjalnie. Aczkolwiek,
    zostawiam ją z przyczyn historycznych, w ten sposób można łatwo
    wyłowić klasy edycyjne, które grzebią COKOLWIEK w cache.
    """

    # Mój dynks do grappelli
    auto_open_collapsibles = True

    def save_formset(self, *args, **kw):
        super(CommitedModelAdmin, self).save_formset(*args, **kw)
        # transaction.commit()


class Charakter_FormalnyAdmin(CommitedModelAdmin):
    list_display = ['skrot', 'nazwa', 'publikacja', 'streszczenie']
    list_filter = ('publikacja', 'streszczenie')
    search_fields = ['skrot', 'nazwa']


admin.site.register(Charakter_Formalny, Charakter_FormalnyAdmin)


class NazwaISkrotAdmin(CommitedModelAdmin):
    list_display = ['skrot', 'nazwa']


admin.site.register(Tytul, NazwaISkrotAdmin)
admin.site.register(Typ_KBN, NazwaISkrotAdmin)


class Typ_OdpowiedzialnosciAdmin(CommitedModelAdmin):
    list_display = ['nazwa', 'skrot']


admin.site.register(Typ_Odpowiedzialnosci, Typ_OdpowiedzialnosciAdmin)
# Uczelnia

class UczelniaAdmin(ZapiszZAdnotacjaMixin, CommitedModelAdmin):
    fieldsets = (
        (None, {
            'fields': (
            'nazwa', 'nazwa_dopelniacz_field', 'skrot', 'logo_www', 'logo_svg'),
        }),
        ADNOTACJE_FIELDSET
    )


admin.site.register(Uczelnia, UczelniaAdmin)

# Wydział

class WydzialAdmin(ZapiszZAdnotacjaMixin, CommitedModelAdmin):
    list_display = ['nazwa', 'skrot', 'uczelnia', 'kolejnosc']
    fieldsets = (
        (None, {
            'fields': ('uczelnia', 'nazwa', 'skrot', 'opis', 'kolejnosc'),
        }),
        HISTORYCZNY_FIELDSET,
        ADNOTACJE_FIELDSET
    )


admin.site.register(Wydzial, WydzialAdmin)


# Autor_Jednostka

class Autor_JednostkaInline(admin.TabularInline):
    model = Autor_Jednostka
    form = autocomplete_light.modelform_factory(Autor_Jednostka)
    extra = 1


# Jednostka

class JednostkaAdmin(ZapiszZAdnotacjaMixin, CommitedModelAdmin):
    list_display = ('nazwa', 'skrot', 'wydzial', 'widoczna',
                    'wchodzi_do_raportow')
    fields = None
    list_filter = ('wydzial', 'widoczna', 'wchodzi_do_raportow')
    search_fields = ['nazwa', 'skrot', 'wydzial__nazwa']
    # inlines = [Autor_JednostkaInline,]
    fieldsets = (
        (None, {
            'fields': (
                'nazwa', 'skrot', 'wydzial', 'opis', 'widoczna',
                'wchodzi_do_raportow', 'email', 'www'),
        }),
        HISTORYCZNY_FIELDSET,
        ADNOTACJE_FIELDSET)


admin.site.register(Jednostka, JednostkaAdmin)


# Autorzy

class AutorAdmin(ZapiszZAdnotacjaMixin, CommitedModelAdmin):
    list_display = ['nazwisko', 'imiona', 'tytul', 'poprzednie_nazwiska',
                    'email']
    fields = None
    inlines = [Autor_JednostkaInline, ]
    list_filter = ['jednostki', 'jednostki__wydzial']
    search_fields = ['imiona', 'nazwisko', 'poprzednie_nazwiska', 'email',
                     'www']
    fieldsets = (
        (None, {
            'fields': (
                'imiona', 'nazwisko', 'tytul', 'pokazuj_na_stronach_jednostek',
                'email', 'www')
        }),
        ('Biografia', {
            'classes': ('grp-collapse grp-closed',),
            'fields': ('urodzony', 'zmarl', 'poprzednie_nazwiska')
        }),
        ADNOTACJE_FIELDSET)


admin.site.register(Autor, AutorAdmin)

# Źródła indeksowane

class Punktacja_ZrodlaForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(Punktacja_ZrodlaForm, self).__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].help_text = ''


class Punktacja_ZrodlaInline(admin.TabularInline):
    model = Punktacja_Zrodla
    form = Punktacja_ZrodlaForm
    fields = ['rok', 'impact_factor', 'punkty_kbn', 'index_copernicus',
              'punktacja_wewnetrzna', 'kc_impact_factor', 'kc_punkty_kbn',
              'kc_index_copernicus']
    extra = 1


class Redakcja_ZrodlaInline(admin.TabularInline):
    model = Redakcja_Zrodla
    extra = 1
    form = autocomplete_light.modelform_factory(Redakcja_Zrodla)


class ZrodloAdmin(ZapiszZAdnotacjaMixin, CommitedModelAdmin):
    fields = None
    inlines = (Punktacja_ZrodlaInline, Redakcja_ZrodlaInline,)
    search_fields = ['nazwa', 'skrot', 'issn', 'e_issn', 'www',
                     'poprzednia_nazwa']
    list_display = ['nazwa', 'skrot', 'rodzaj', 'www']
    list_filter = ['rodzaj', 'zasieg']
    fieldsets = (
        (None, {
            'fields': (
                'rodzaj', 'nazwa', 'skrot', 'issn', 'e_issn', 'www', 'zasieg',
                'poprzednia_nazwa'),
        }),
        ADNOTACJE_FIELDSET)


admin.site.register(Zrodlo, ZrodloAdmin)

# Bibliografia
from django.forms.widgets import HiddenInput


def generuj_inline_dla_autorow(baseModel):
    class baseModel_AutorForm(forms.ModelForm):
        class Media:
            js = (
                "../dynjs/autorform_dependant.js?class=%s" % baseModel.__name__, )

        class Meta:
            model = baseModel
            widgets = dict(
                autocomplete_light.get_widgets_dict(baseModel).items() +
                [('zapisany_jako', autocomplete_light.TextWidget(
                    'AutocompleteZapisaneNazwiska')),
                 ('kolejnosc', HiddenInput)])

    class baseModel_AutorInline(admin.TabularInline):
        model = baseModel
        extra = 1
        form = baseModel_AutorForm
        sortable_field_name = "kolejnosc"

    return baseModel_AutorInline

#
# Wydaniwcto Ciągłe
#


# Widget do automatycznego uzupełniania punktacji wydawnictwa ciągłego

class Button(forms.Widget):
    """
    A widget that handles a submit button.
    """

    def __init__(self, name, label, attrs):
        self.name, self.label = name, label
        self.attrs = attrs

    def __unicode__(self):
        final_attrs = self.build_attrs(
            self.attrs,
            type="button",
            name=self.name)

        return mark_safe(u'<button%s>%s</button>' % (
            forms.widgets.flatatt(final_attrs),
            self.label,
        ))


Wydawnictwo_Ciagle_Form = autocomplete_light.modelform_factory(
    Wydawnictwo_Ciagle)
Wydawnictwo_Ciagle_Form.base_fields['uzupelnij_punktacje'] = \
    forms.Field(
        'uzupelnij_punktacje', widget=Button(
            'uzupelnij_punktacje',
            'Uzupełnij punktację',
            {'id': 'uzupelnij_punktacje'}))


class Wydawnictwo_CiagleAdmin(ZapiszZAdnotacjaMixin, CommitedModelAdmin):

    formfield_overrides = NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW

    form = Wydawnictwo_Ciagle_Form

    list_display = ['tytul_oryginalny', 'zrodlo', 'rok',
                    'typ_kbn', 'charakter_formalny', 'ostatnio_zmieniony']

    search_fields = [
        'tytul', 'tytul_oryginalny', 'szczegoly', 'uwagi', 'informacje',
        'slowa_kluczowe', 'rok',
        'issn', 'e_issn', 'zrodlo__nazwa', 'zrodlo__skrot', 'adnotacje']

    list_filter = ['status_korekty', 'afiliowana', 'recenzowana', 'typ_kbn',
                   'charakter_formalny']

    fieldsets = (
        ('Wydawnictwo ciągłe', {
            'fields':
                DWA_TYTULY
                + ('zrodlo', )
                + MODEL_ZE_SZCZEGOLAMI
                + MODEL_Z_ROKIEM
        }),
        EKSTRA_INFORMACJE_WYDAWNICTWO_CIAGLE_FIELDSET,
        MODEL_TYPOWANY_FIELDSET,
        MODEL_PUNKTOWANY_WYDAWNICTWO_CIAGLE_FIELDSET,
        MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET,
        POZOSTALE_MODELE_FIELDSET,
        ADNOTACJE_FIELDSET)

    inlines = (
        generuj_inline_dla_autorow(Wydawnictwo_Ciagle_Autor),
    )


admin.site.register(Wydawnictwo_Ciagle, Wydawnictwo_CiagleAdmin)


class Wydawnictwo_ZwarteAdmin_Baza(ZapiszZAdnotacjaMixin, CommitedModelAdmin):
    formfield_overrides = NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW

    list_display = ['tytul_oryginalny', 'wydawnictwo', 'typ_kbn',
                    'charakter_formalny', 'ostatnio_zmieniony']

    search_fields = [
        'tytul', 'tytul_oryginalny', 'szczegoly', 'uwagi', 'informacje',
        'slowa_kluczowe', 'rok',
        'wydawnictwo', 'redakcja', 'adnotacje']

    list_filter = ['status_korekty', 'afiliowana', 'recenzowana', 'typ_kbn',
                   'charakter_formalny', 'liczba_znakow_wydawniczych']

    fieldsets = (
        ('Wydawnictwo zwarte', {
            'fields':
                DWA_TYTULY
                + MODEL_ZE_SZCZEGOLAMI
                + ('miejsce_i_rok', 'wydawnictwo',)
                + MODEL_Z_ROKIEM
        }),
        EKSTRA_INFORMACJE_WYDAWNICTWO_ZWARTE_FIELDSET,
        MODEL_TYPOWANY_FIELDSET,
        MODEL_PUNKTOWANY_FIELDSET,
        MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET,
        POZOSTALE_MODELE_FIELDSET,
        ADNOTACJE_FIELDSET)


class Wydawnictwo_ZwarteAdmin(Wydawnictwo_ZwarteAdmin_Baza):
    form = autocomplete_light.modelform_factory(Wydawnictwo_Zwarte)
    inlines = (generuj_inline_dla_autorow(Wydawnictwo_Zwarte_Autor),)

    fieldsets = (
        ('Wydawnictwo zwarte', {
            'fields':
                DWA_TYTULY
                + MODEL_ZE_SZCZEGOLAMI
                + ('wydawnictwo_nadrzedne', 'miejsce_i_rok', 'wydawnictwo',)
                + MODEL_Z_ROKIEM
                + ('liczba_znakow_wydawniczych',)
        }),
        EKSTRA_INFORMACJE_WYDAWNICTWO_ZWARTE_FIELDSET,
        MODEL_TYPOWANY_FIELDSET,
        MODEL_PUNKTOWANY_FIELDSET,
        MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET,
        POZOSTALE_MODELE_FIELDSET,
        ADNOTACJE_FIELDSET)


admin.site.register(Wydawnictwo_Zwarte, Wydawnictwo_ZwarteAdmin)

DOKTORSKA_HABILITACYJNA_FIELDS = DWA_TYTULY \
                                 + MODEL_ZE_SZCZEGOLAMI \
                                 + (
    'miejsce_i_rok', 'wydawnictwo', 'autor', 'jednostka') \
                                 + MODEL_Z_ROKIEM


class Praca_Doktorska_Habilitacyjna_Admin_Base(ZapiszZAdnotacjaMixin,
                                               CommitedModelAdmin):
    formfield_overrides = NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW

    form = autocomplete_light.modelform_factory(Praca_Doktorska)

    list_display = [
        'tytul_oryginalny', 'autor', 'jednostka', 'wydawnictwo',
        'typ_kbn', 'ostatnio_zmieniony']

    search_fields = [
        'tytul', 'tytul_oryginalny', 'szczegoly', 'uwagi', 'informacje',
        'slowa_kluczowe', 'rok', 'www', 'wydawnictwo', 'redakcja',
        'autor__tytul__nazwa', 'jednostka__nazwa', 'adnotacje']

    list_filter = ['status_korekty', 'afiliowana', 'recenzowana', 'typ_kbn']


class Praca_DoktorskaAdmin(Praca_Doktorska_Habilitacyjna_Admin_Base):
    fieldsets = (
        ('Praca doktorska', {
            'fields': DOKTORSKA_HABILITACYJNA_FIELDS
        }),
        EKSTRA_INFORMACJE_WYDAWNICTWO_ZWARTE_FIELDSET,
        MODEL_TYPOWANY_BEZ_CHARAKTERU_FIELDSET,
        MODEL_PUNKTOWANY_FIELDSET,
        MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET,
        POZOSTALE_MODELE_FIELDSET,
        ADNOTACJE_FIELDSET)


admin.site.register(Praca_Doktorska, Praca_DoktorskaAdmin)

#
# Praca Habilitacyjna
#

class Publikacja_Habilitacyjna_Form(forms.ModelForm):
    class Meta:
        model = Publikacja_Habilitacyjna
        widgets = dict(
            autocomplete_light.get_widgets_dict(
                Publikacja_Habilitacyjna).items() +
            [('kolejnosc', HiddenInput)])


class Publikacja_Habilitacyjna_Inline(admin.TabularInline):
    model = Publikacja_Habilitacyjna
    form = Publikacja_Habilitacyjna_Form  # autocomplete_light.modelform_factory(Publikacja_Habilitacyjna)
    extra = 1
    sortable_field_name = "kolejnosc"


class Praca_HabilitacyjnaAdmin(Praca_Doktorska_Habilitacyjna_Admin_Base):
    inlines = [Publikacja_Habilitacyjna_Inline, ]
    form = autocomplete_light.modelform_factory(Praca_Habilitacyjna)
    fieldsets = (
        ('Praca habilitacyjna', {
            'fields': DOKTORSKA_HABILITACYJNA_FIELDS
        }),
        EKSTRA_INFORMACJE_WYDAWNICTWO_ZWARTE_FIELDSET,
        MODEL_TYPOWANY_BEZ_CHARAKTERU_FIELDSET,
        MODEL_PUNKTOWANY_FIELDSET,
        MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET,
        POZOSTALE_MODELE_FIELDSET,
        ADNOTACJE_FIELDSET)


admin.site.register(Praca_Habilitacyjna, Praca_HabilitacyjnaAdmin)


class Patent_Admin(Wydawnictwo_ZwarteAdmin_Baza):
    form = autocomplete_light.modelform_factory(Patent)
    inlines = (generuj_inline_dla_autorow(Patent_Autor),)

    list_display = ['tytul_oryginalny', 'ostatnio_zmieniony']

    search_fields = [
        'tytul_oryginalny', 'szczegoly', 'uwagi', 'informacje',
        'slowa_kluczowe', 'rok', 'adnotacje']

    list_filter = ['status_korekty', 'afiliowana', 'recenzowana', ]

    fieldsets = (
        ('Patent', {
            'fields':
                ('tytul_oryginalny', )
                + MODEL_ZE_SZCZEGOLAMI
                + ('numer', 'z_dnia',)
                + MODEL_Z_ROKIEM
                + MODEL_Z_WWW
        }),
        MODEL_PUNKTOWANY_FIELDSET,
        MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET,
        POZOSTALE_MODELE_FIELDSET,
        ADNOTACJE_FIELDSET)


admin.site.register(Patent, Patent_Admin)

from django.contrib.auth.admin import UserAdmin

admin.site.register(BppUser, UserAdmin)