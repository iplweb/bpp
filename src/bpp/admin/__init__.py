# -*- encoding: utf-8 -*-
import autocomplete_light
from django import forms
from django.contrib import admin
from django.contrib.admin.filters import SimpleListFilter
from django.contrib.auth.forms import UserCreationForm
from django.db.models.fields import BLANK_CHOICE_DASH
from multiseek.models import SearchForm

from bpp.admin.filters import LiczbaZnakowFilter, CalkowitaLiczbaAutorowFilter, JednostkaFilter, PBNIDObecnyFilter, \
    PeselMD5ObecnyFilter
from bpp.admin.helpers import *
from bpp.models import Jezyk, Typ_KBN, Uczelnia, Wydzial, \
    Jednostka, Tytul, Autor, Autor_Jednostka, Funkcja_Autora, Rodzaj_Zrodla, \
    Zrodlo, Punktacja_Zrodla, Typ_Odpowiedzialnosci, Status_Korekty, \
    Zrodlo_Informacji, Wydawnictwo_Ciagle, Charakter_Formalny, \
    Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor, Praca_Doktorska, \
    Praca_Habilitacyjna, Patent, Patent_Autor, BppUser, Publikacja_Habilitacyjna

# Proste tabele
from bpp.models.openaccess import Tryb_OpenAccess_Wydawnictwo_Ciagle, Tryb_OpenAccess_Wydawnictwo_Zwarte, \
    Czas_Udostepnienia_OpenAccess, Licencja_OpenAccess, Wersja_Tekstu_OpenAccess
from bpp.models.struktura import Jednostka_Wydzial
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor
from bpp.models.zrodlo import Redakcja_Zrodla


class BaseBppAdmin(admin.ModelAdmin):
    pass


class RestrictDeletionToAdministracjaGroupMixin:
    def get_action_choices(self, request, default_choices=BLANK_CHOICE_DASH):
        if 'administracja' in [x.name for x in request.user.groups.all()]:
            return admin.ModelAdmin.get_action_choices(self, request, default_choices)
        return []

    def has_delete_permission(self, request, obj=None):
        if 'administracja' in [x.name for x in request.user.groups.all()]:
            return admin.ModelAdmin.has_delete_permission(self, request, obj=obj)
        return False


class RestrictDeletionToAdministracjaGroupAdmin(
        RestrictDeletionToAdministracjaGroupMixin, admin.ModelAdmin):
    pass


class JezykAdmin(RestrictDeletionToAdministracjaGroupAdmin):
    list_display = ['nazwa', 'skrot', 'skrot_dla_pbn']


admin.site.register(Jezyk, JezykAdmin)
admin.site.register(Funkcja_Autora, RestrictDeletionToAdministracjaGroupAdmin)
admin.site.register(Rodzaj_Zrodla, RestrictDeletionToAdministracjaGroupAdmin)
admin.site.register(Status_Korekty, RestrictDeletionToAdministracjaGroupAdmin)
admin.site.register(Zrodlo_Informacji, RestrictDeletionToAdministracjaGroupAdmin)


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


class Charakter_FormalnyAdmin(RestrictDeletionToAdministracjaGroupMixin, CommitedModelAdmin):
    list_display = ['skrot', 'nazwa', 'publikacja', 'streszczenie', 'nazwa_w_primo',
                    'charakter_pbn', 'artykul_pbn', 'ksiazka_pbn', 'rozdzial_pbn']
    list_filter = ('publikacja', 'streszczenie', 'nazwa_w_primo', 'charakter_pbn',
                   'artykul_pbn', 'ksiazka_pbn', 'rozdzial_pbn')
    search_fields = ['skrot', 'nazwa']


admin.site.register(Charakter_Formalny, Charakter_FormalnyAdmin)


class NazwaISkrotAdmin(RestrictDeletionToAdministracjaGroupMixin, CommitedModelAdmin):
    list_display = ['skrot', 'nazwa']
    search_fields = ['skrot', 'nazwa']


admin.site.register(Tytul, NazwaISkrotAdmin)

class Typ_KBNAdmin(RestrictDeletionToAdministracjaGroupAdmin, CommitedModelAdmin):
    list_display = ['nazwa', 'skrot', 'artykul_pbn']

admin.site.register(Typ_KBN, Typ_KBNAdmin)


class Typ_OdpowiedzialnosciAdmin(RestrictDeletionToAdministracjaGroupMixin, CommitedModelAdmin):
    list_display = ['nazwa', 'skrot']


class Tryb_OpenAccess_Wydawnictwo_CiagleAdmin(RestrictDeletionToAdministracjaGroupMixin, CommitedModelAdmin):
    list_display = ['nazwa', 'skrot']


admin.site.register(Tryb_OpenAccess_Wydawnictwo_Ciagle, Tryb_OpenAccess_Wydawnictwo_CiagleAdmin)


class Tryb_OpenAccess_Wydawnictwo_ZwarteAdmin(RestrictDeletionToAdministracjaGroupMixin, CommitedModelAdmin):
    list_display = ['nazwa', 'skrot']


admin.site.register(Tryb_OpenAccess_Wydawnictwo_Zwarte, Tryb_OpenAccess_Wydawnictwo_ZwarteAdmin)


class Czas_Udostepnienia_OpenAccessAdmin(RestrictDeletionToAdministracjaGroupMixin, CommitedModelAdmin):
    list_display = ['nazwa', 'skrot']


admin.site.register(Czas_Udostepnienia_OpenAccess, Czas_Udostepnienia_OpenAccessAdmin)


class Licencja_OpenAccessAdmin(RestrictDeletionToAdministracjaGroupMixin, CommitedModelAdmin):
    list_display = ['nazwa', 'skrot']


admin.site.register(Licencja_OpenAccess, Licencja_OpenAccessAdmin)


class Wersja_Tekstu_OpenAccessAdmin(RestrictDeletionToAdministracjaGroupMixin, CommitedModelAdmin):
    list_display = ['nazwa', 'skrot']


admin.site.register(Wersja_Tekstu_OpenAccess, Wersja_Tekstu_OpenAccessAdmin)

admin.site.register(Typ_Odpowiedzialnosci, Typ_OdpowiedzialnosciAdmin)


# Uczelnia

class UczelniaAdmin(RestrictDeletionToAdministracjaGroupMixin, ZapiszZAdnotacjaMixin, CommitedModelAdmin):
    list_display = ['nazwa', 'nazwa_dopelniacz_field', 'skrot', 'pbn_id']
    fieldsets = (
        (None, {
            'fields': (
                'nazwa', 'nazwa_dopelniacz_field', 'skrot', 'pbn_id', 'logo_www', 'logo_svg', 'favicon_ico',
                'obca_jednostka'),
        }),
        ADNOTACJE_FIELDSET
    )


admin.site.register(Uczelnia, UczelniaAdmin)


# Wydział

class WydzialAdmin(RestrictDeletionToAdministracjaGroupMixin, ZapiszZAdnotacjaMixin, CommitedModelAdmin):
    list_display = ['nazwa', 'skrot', 'uczelnia', 'kolejnosc', 'widoczny', 'ranking_autorow',
                    'zarzadzaj_automatycznie', 'otwarcie', 'zamkniecie', 'pbn_id']
    list_filter = ['uczelnia', 'zezwalaj_na_ranking_autorow', 'widoczny', 'zarzadzaj_automatycznie',]
    fieldsets = (
        (None, {
            'fields': (
                'uczelnia', 'nazwa', 'skrot', 'pbn_id', 'opis', 'kolejnosc', 'widoczny',
                'zezwalaj_na_ranking_autorow', 'zarzadzaj_automatycznie', 'otwarcie', 'zamkniecie'),
        }),
        ADNOTACJE_FIELDSET
    )

    def ranking_autorow(self, obj):
        return obj.zezwalaj_na_ranking_autorow
    ranking_autorow.short_description = "Ranking autorów"
    ranking_autorow.boolean = True
    ranking_autorow.admin_order_field = 'zezwalaj_na_ranking_autorow'


admin.site.register(Wydzial, WydzialAdmin)


# Autor_Jednostka

class Autor_JednostkaInline(admin.TabularInline):
    model = Autor_Jednostka
    form = autocomplete_light.modelform_factory(Autor_Jednostka, fields="__all__")
    extra = 1


# Jednostka

class Jednostka_WydzialInline(admin.TabularInline):
    model = Jednostka_Wydzial
    extra = 1

class JednostkaAdmin(RestrictDeletionToAdministracjaGroupMixin, ZapiszZAdnotacjaMixin, CommitedModelAdmin):
    list_display = ('nazwa', 'skrot', 'wydzial', 'widoczna',
                    'wchodzi_do_raportow', 'skupia_pracownikow', 'zarzadzaj_automatycznie', 'pbn_id')
    list_select_related = ['wydzial',]
    fields = None
    list_filter = ('wydzial', 'widoczna', 'wchodzi_do_raportow', 'skupia_pracownikow', 'zarzadzaj_automatycznie')
    search_fields = ['nazwa', 'skrot', 'wydzial__nazwa']

    inlines = (Jednostka_WydzialInline,
               # Autor_JednostkaInline,
               )

    readonly_fields = ['wydzial', 'aktualna', 'ostatnio_zmieniony']
    fieldsets = (
        (None, {
            'fields': (
                'nazwa', 'skrot', 'uczelnia', 'wydzial', 'aktualna',
                'pbn_id', 'opis', 'widoczna',
                'wchodzi_do_raportow', 'skupia_pracownikow',
                'zarzadzaj_automatycznie', 'email', 'www'),
        }),
        ADNOTACJE_FIELDSET)

admin.site.register(Jednostka, JednostkaAdmin)

# Autorzy

CHARMAP_SINGLE_LINE = forms.TextInput(
        attrs={'class': 'charmap', 'style': "width: 500px"})


class AutorForm(forms.ModelForm):
    class Meta:
        fields = "__all__"
        model = Autor
        widgets = {
            'imiona': CHARMAP_SINGLE_LINE,
            'nazwisko': CHARMAP_SINGLE_LINE
        }


class AutorAdmin(ZapiszZAdnotacjaMixin, CommitedModelAdmin):
    form = AutorForm

    list_display = ['nazwisko', 'imiona', 'tytul', 'poprzednie_nazwiska', 'email', 'pbn_id']
    list_select_related = ['tytul',]
    fields = None
    inlines = [Autor_JednostkaInline, ]
    list_filter = [JednostkaFilter, 'aktualna_jednostka__wydzial', 'tytul', PBNIDObecnyFilter, PeselMD5ObecnyFilter]
    search_fields = ['imiona', 'nazwisko', 'poprzednie_nazwiska', 'email', 'www', 'id', 'pbn_id']
    readonly_fields = ('pesel_md5', 'ostatnio_zmieniony')

    fieldsets = (
        (None, {
            'fields': (
                'imiona', 'nazwisko', 'tytul', 'pokazuj_na_stronach_jednostek',
                'email', 'www', 'pbn_id', 'pesel_md5')
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
    form = autocomplete_light.modelform_factory(Redakcja_Zrodla, fields="__all__")


class ZrodloForm(forms.ModelForm):
    class Meta:
        model = Zrodlo
        widgets = {
            'nazwa': CHARMAP_SINGLE_LINE,
            'skrot': CHARMAP_SINGLE_LINE,
            'nazwa_alternatywna': CHARMAP_SINGLE_LINE,
            'skrot_nazwy_alternatywnej': CHARMAP_SINGLE_LINE,
            'poprzednia_nazwa': CHARMAP_SINGLE_LINE
        }
        fields = "__all__"


class ZrodloAdmin(ZapiszZAdnotacjaMixin, CommitedModelAdmin):
    form = ZrodloForm

    fields = None
    inlines = (Punktacja_ZrodlaInline, Redakcja_ZrodlaInline,)
    search_fields = ['nazwa', 'skrot', 'nazwa_alternatywna',
                     'skrot_nazwy_alternatywnej', 'issn', 'e_issn', 'www',
                     'poprzednia_nazwa', 'doi']
    list_display = ['nazwa', 'skrot', 'rodzaj', 'www', 'issn', 'e_issn']
    list_filter = ['rodzaj', 'zasieg', 'openaccess_tryb_dostepu', 'openaccess_licencja']
    list_select_related = ['openaccess_licencja', 'rodzaj']
    fieldsets = (
        (None, {
            'fields': (
                'nazwa', 'skrot', 'rodzaj', 'nazwa_alternatywna',
                'skrot_nazwy_alternatywnej', 'issn', 'e_issn', 'www', 'doi',
                'zasieg', 'poprzednia_nazwa', 'jezyk', 'wydawca',),
        }),
        ADNOTACJE_FIELDSET,
        ("OpenAccess", {
            'classes': ('grp-collapse grp-closed',),
            'fields': ('openaccess_tryb_dostepu', 'openaccess_licencja',)
        })
    )


admin.site.register(Zrodlo, ZrodloAdmin)

# Bibliografia
from django.forms.widgets import HiddenInput


def generuj_inline_dla_autorow(baseModel):
    class baseModel_AutorForm(autocomplete_light.ModelForm):
        class Media:
            js = (
                "../dynjs/autorform_dependant.js?class=%s" % baseModel.__name__,)

        class Meta:
            fields = ["autor", "jednostka", "typ_odpowiedzialnosci", "zapisany_jako",
                      "zatrudniony", "kolejnosc"]
            model = baseModel
            widgets = {
                'zapisany_jako': autocomplete_light.TextWidget(
                        'AutocompleteZapisaneNazwiska'),
                'kolejnosc': HiddenInput
            }

    class baseModel_AutorInline(admin.TabularInline):
        model = baseModel
        extra = 1
        form = baseModel_AutorForm
        sortable_field_name = "kolejnosc"

    return baseModel_AutorInline


#
# Kolumny ze skrótami
#

class KolumnyZeSkrotamiMixin:
    def charakter_formalny__skrot(self, obj):
        return obj.charakter_formalny.skrot
    charakter_formalny__skrot.short_description = "Char. form."
    charakter_formalny__skrot.admin_order_field = "charakter_formalny__skrot"

    def typ_kbn__skrot(self, obj):
        return obj.typ_kbn.skrot
    typ_kbn__skrot.short_description = "Typ KBN"
    typ_kbn__skrot.admin_order_field = "typ_kbn__skrot"

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
        Wydawnictwo_Ciagle, fields="__all__")
Wydawnictwo_Ciagle_Form.base_fields['uzupelnij_punktacje'] = \
    forms.Field(
            'uzupelnij_punktacje', widget=Button(
                    'uzupelnij_punktacje',
                    'Uzupełnij punktację',
                    {'id': 'uzupelnij_punktacje'}))

class Wydawnictwo_CiagleAdmin(KolumnyZeSkrotamiMixin, AdnotacjeZDatamiOrazPBNMixin, CommitedModelAdmin):
    formfield_overrides = NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW

    form = Wydawnictwo_Ciagle_Form

    list_display = ['tytul_oryginalny', 'zrodlo_col', 'rok',
                    'typ_kbn__skrot', 'charakter_formalny__skrot', 'liczba_znakow_wydawniczych',
                    'ostatnio_zmieniony']

    list_select_related = ['zrodlo', 'typ_kbn', 'charakter_formalny']

    search_fields = [
        'tytul', 'tytul_oryginalny', 'szczegoly', 'uwagi', 'informacje',
        'slowa_kluczowe', 'rok', 'id',
        'issn', 'e_issn', 'zrodlo__nazwa', 'zrodlo__skrot', 'adnotacje',
        'liczba_znakow_wydawniczych']

    list_filter = ['status_korekty', 'afiliowana', 'recenzowana', 'typ_kbn',
                   'charakter_formalny', 'jezyk', LiczbaZnakowFilter, 'rok']

    fieldsets = (
        ('Wydawnictwo ciągłe', {
            'fields':
                DWA_TYTULY
                + ('zrodlo',)
                + MODEL_ZE_SZCZEGOLAMI
                + MODEL_Z_ROKIEM
        }),
        EKSTRA_INFORMACJE_WYDAWNICTWO_CIAGLE_FIELDSET,
        MODEL_TYPOWANY_FIELDSET,
        MODEL_PUNKTOWANY_WYDAWNICTWO_CIAGLE_FIELDSET,
        MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET,
        POZOSTALE_MODELE_WYDAWNICTWO_CIAGLE_FIELDSET,
        ADNOTACJE_Z_DATAMI_ORAZ_PBN_FIELDSET,
        OPENACCESS_FIELDSET)

    inlines = (
        generuj_inline_dla_autorow(Wydawnictwo_Ciagle_Autor),
    )

    def zrodlo_col(self, obj):
        try:
            return obj.zrodlo.nazwa
        except Zrodlo.DoesNotExist:
            return ''
    zrodlo_col.admin_order_field = 'zrodlo__nazwa'
    zrodlo_col.short_description = "Źródło"



admin.site.register(Wydawnictwo_Ciagle, Wydawnictwo_CiagleAdmin)


class Wydawnictwo_ZwarteAdmin_Baza(CommitedModelAdmin):
    formfield_overrides = NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW

    list_display = ['tytul_oryginalny', 'wydawnictwo',
                    'wydawnictwo_nadrzedne_col',
                    'rok',
                    'typ_kbn__skrot',
                    'charakter_formalny__skrot',
                    'liczba_znakow_wydawniczych',
                    'ostatnio_zmieniony']

    search_fields = [
        'tytul', 'tytul_oryginalny', 'szczegoly', 'uwagi', 'informacje',
        'slowa_kluczowe', 'rok', 'isbn', 'id',
        'wydawnictwo', 'redakcja', 'adnotacje',
        'liczba_znakow_wydawniczych',
        'wydawnictwo_nadrzedne__tytul_oryginalny']

    list_filter = ['status_korekty', 'afiliowana', 'recenzowana', 'typ_kbn',
                   'charakter_formalny', 'informacja_z', 'jezyk', LiczbaZnakowFilter, 'rok']

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
        ADNOTACJE_Z_DATAMI_ORAZ_PBN_FIELDSET)

    def wydawnictwo_nadrzedne_col(self, obj):
        try:
            return obj.wydawnictwo_nadrzedne.tytul_oryginalny
        except Wydawnictwo_Zwarte.DoesNotExist:
            return ''
        except AttributeError:
            return ''
    wydawnictwo_nadrzedne_col.short_description = "Wydawnictwo nadrzędne"
    wydawnictwo_nadrzedne_col.admin_order_field = "wydawnictwo_nadrzedne__tytul_oryginalny"



class Wydawnictwo_ZwarteAdmin(KolumnyZeSkrotamiMixin, AdnotacjeZDatamiOrazPBNMixin, Wydawnictwo_ZwarteAdmin_Baza):
    form = autocomplete_light.modelform_factory(Wydawnictwo_Zwarte, fields="__all__")
    inlines = (generuj_inline_dla_autorow(Wydawnictwo_Zwarte_Autor),)

    list_filter = Wydawnictwo_ZwarteAdmin_Baza.list_filter + [CalkowitaLiczbaAutorowFilter,]

    list_select_related = ['charakter_formalny', 'typ_kbn', 'wydawnictwo_nadrzedne',]

    fieldsets = (
        ('Wydawnictwo zwarte', {
            'fields':
                DWA_TYTULY
                + MODEL_ZE_SZCZEGOLAMI
                + ('wydawnictwo_nadrzedne', 'calkowita_liczba_autorow', 'miejsce_i_rok', 'wydawnictwo',)
                + MODEL_Z_ROKIEM
        }),
        EKSTRA_INFORMACJE_WYDAWNICTWO_ZWARTE_FIELDSET,
        MODEL_TYPOWANY_FIELDSET,
        MODEL_PUNKTOWANY_FIELDSET,
        MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET,
        POZOSTALE_MODELE_WYDAWNICTWO_ZWARTE_FIELDSET,
        ADNOTACJE_Z_DATAMI_ORAZ_PBN_FIELDSET,
        OPENACCESS_FIELDSET)


admin.site.register(Wydawnictwo_Zwarte, Wydawnictwo_ZwarteAdmin)

DOKTORSKA_FIELDS = DWA_TYTULY \
                   + MODEL_ZE_SZCZEGOLAMI \
                   + ('miejsce_i_rok', 'wydawnictwo', 'autor', 'jednostka', 'promotor') \
                   + MODEL_Z_ROKIEM

HABILITACYJNA_FIELDS = DWA_TYTULY \
                       + MODEL_ZE_SZCZEGOLAMI \
                       + ('miejsce_i_rok', 'wydawnictwo', 'autor', 'jednostka') \
                       + MODEL_Z_ROKIEM


class Praca_Doktorska_Habilitacyjna_Admin_Base(AdnotacjeZDatamiMixin,
                                               CommitedModelAdmin):
    formfield_overrides = NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW

    list_display = [
        'tytul_oryginalny', 'autor', 'jednostka', 'wydawnictwo',
        'typ_kbn', 'ostatnio_zmieniony']
    list_select_related = ['autor', 'autor__tytul', 'jednostka', 'jednostka__wydzial', 'typ_kbn']

    search_fields = [
        'tytul', 'tytul_oryginalny', 'szczegoly', 'uwagi', 'informacje',
        'slowa_kluczowe', 'rok', 'www', 'wydawnictwo', 'redakcja',
        'autor__tytul__nazwa', 'jednostka__nazwa', 'adnotacje', 'id', ]

    list_filter = ['status_korekty', 'afiliowana', 'recenzowana', 'typ_kbn']


class Praca_DoktorskaForm(autocomplete_light.ModelForm):
    class Meta:
        model = Praca_Doktorska
        fields = "__all__"


class Praca_DoktorskaAdmin(Praca_Doktorska_Habilitacyjna_Admin_Base):
    form = Praca_DoktorskaForm

    fieldsets = (
        ('Praca doktorska', {
            'fields': DOKTORSKA_FIELDS
        }),
        EKSTRA_INFORMACJE_WYDAWNICTWO_ZWARTE_FIELDSET,
        MODEL_TYPOWANY_BEZ_CHARAKTERU_FIELDSET,
        MODEL_PUNKTOWANY_FIELDSET,
        MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET,
        POZOSTALE_MODELE_FIELDSET,
        ADNOTACJE_Z_DATAMI_FIELDSET)


admin.site.register(Praca_Doktorska, Praca_DoktorskaAdmin)


#
# Praca Habilitacyjna
#
#
class Publikacja_Habilitacyjna_Form(forms.ModelForm):
    class Meta:
        model = Publikacja_Habilitacyjna
        widgets = {'kolejnosc': HiddenInput}
        fields = "__all__"


class Publikacja_Habilitacyjna_Inline(admin.TabularInline):
    model = Publikacja_Habilitacyjna
    form = Publikacja_Habilitacyjna_Form
    extra = 1
    sortable_field_name = "kolejnosc"

    related_lookup_fields = {
        'generic': [['content_type', 'object_id']],
    }


class Praca_HabilitacyjnaAdmin(Praca_Doktorska_Habilitacyjna_Admin_Base):
    inlines = [Publikacja_Habilitacyjna_Inline, ]

    form = autocomplete_light.modelform_factory(Praca_Habilitacyjna, fields="__all__")

    fieldsets = (
        ('Praca habilitacyjna', {
            'fields': HABILITACYJNA_FIELDS
        }),
        EKSTRA_INFORMACJE_WYDAWNICTWO_ZWARTE_FIELDSET,
        MODEL_TYPOWANY_BEZ_CHARAKTERU_FIELDSET,
        MODEL_PUNKTOWANY_FIELDSET,
        MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET,
        POZOSTALE_MODELE_FIELDSET,
        ADNOTACJE_Z_DATAMI_FIELDSET)


admin.site.register(Praca_Habilitacyjna, Praca_HabilitacyjnaAdmin)


class Patent_Admin(AdnotacjeZDatamiMixin, Wydawnictwo_ZwarteAdmin_Baza):
    form = autocomplete_light.modelform_factory(Patent, fields="__all__")
    inlines = (generuj_inline_dla_autorow(Patent_Autor),)

    list_display = ['tytul_oryginalny', 'ostatnio_zmieniony']

    search_fields = [
        'tytul_oryginalny', 'szczegoly', 'uwagi', 'informacje',
        'slowa_kluczowe', 'rok', 'adnotacje', 'id', ]

    list_filter = ['status_korekty', 'afiliowana', 'recenzowana', ]

    fieldsets = (
        ('Patent', {
            'fields':
                ('tytul_oryginalny',)
                + MODEL_ZE_SZCZEGOLAMI
                + ('numer', 'z_dnia',)
                + MODEL_Z_ROKIEM
                + MODEL_Z_WWW
        }),
        MODEL_PUNKTOWANY_FIELDSET,
        MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET,
        POZOSTALE_MODELE_FIELDSET,
        ADNOTACJE_Z_DATAMI_FIELDSET)


admin.site.register(Patent, Patent_Admin)

from django.contrib.auth.admin import UserAdmin


class BppUserCreationForm(UserCreationForm):
    class Meta:
        model = BppUser
        fields = "__all__"

    def clean_username(self):
        # Since User.username is unique, this check is redundant,
        # but it sets a nicer error message than the ORM. See #13147.
        username = self.cleaned_data["username"]
        try:
            BppUser._default_manager.get(username=username)
        except BppUser.DoesNotExist:
            return username
        raise forms.ValidationError(
                self.error_messages['duplicate_username'],
                code='duplicate_username',
        )


class BppUserAdmin(UserAdmin):
    list_display = (
        'username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'is_superuser', 'lista_grup')

    add_form = BppUserCreationForm

    # change_form_template = 'loginas/change_form.html'

    def lista_grup(self, row):
        return ", ".join([x.name for x in row.groups.all()])


admin.site.register(BppUser, BppUserAdmin)


class SearchFormAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'public']
    fields = ['name', 'owner', 'public', 'data']
    readonly_fields = ['data']


SearchForm._meta.verbose_name = "formularz wyszukiwania"
SearchForm._meta.verbose_name_plural = "formularze wyszukiwania"

admin.site.register(SearchForm, SearchFormAdmin)
