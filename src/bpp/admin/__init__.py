# -*- encoding: utf-8 -*-
from dal.forms import FutureModelForm
from dal_queryset_sequence.fields import QuerySetSequenceModelField
from dal_select2_queryset_sequence.widgets import \
    QuerySetSequenceSelect2
from queryset_sequence import QuerySetSequence

from .core import RestrictDeletionToAdministracjaGroupAdmin, \
    RestrictDeletionToAdministracjaGroupMixin
from ..models.nagroda import OrganPrzyznajacyNagrody

from dal import autocomplete

from django import forms
from django.contrib import admin
from django.forms.widgets import HiddenInput

from django.contrib.auth.forms import UserCreationForm
from django.utils.safestring import mark_safe
from multiseek.models import SearchForm

from .filters import LiczbaZnakowFilter, CalkowitaLiczbaAutorowFilter, \
    JednostkaFilter, PBNIDObecnyFilter, \
    PeselMD5ObecnyFilter, OrcidObecnyFilter
from .helpers import *
from ..models import Jezyk, Typ_KBN, Uczelnia, Wydzial, \
    Jednostka, Tytul, Autor, Autor_Jednostka, Funkcja_Autora, Rodzaj_Zrodla, \
    Zrodlo, Punktacja_Zrodla, Typ_Odpowiedzialnosci, Status_Korekty, \
    Zrodlo_Informacji, Wydawnictwo_Ciagle, Charakter_Formalny, \
    Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor, Praca_Doktorska, \
    Praca_Habilitacyjna, Patent, Patent_Autor, BppUser # Publikacja_Habilitacyjna
from ..models.system import Charakter_PBN

from .core import BaseBppAdmin, CommitedModelAdmin, \
    KolumnyZeSkrotamiMixin, generuj_inline_dla_autorow
from .wydawnictwo_zwarte import Wydawnictwo_ZwarteAdmin_Baza, Wydawnictwo_ZwarteAdmin
from .wydawnictwo_ciagle import Wydawnictwo_CiagleAdmin
from .konferencja import KonferencjaAdmin
from .struktura import UczelniaAdmin, WydzialAdmin, JednostkaAdmin
from .seria_wydawnicza import Seria_WydawniczaAdmin
from .praca_doktorska import Praca_DoktorskaAdmin  # noqa
from .praca_habilitacyjna import Praca_HabilitacyjnaAdmin  # noqa

# Proste tabele
from bpp.models.openaccess import Tryb_OpenAccess_Wydawnictwo_Ciagle, Tryb_OpenAccess_Wydawnictwo_Zwarte, \
    Czas_Udostepnienia_OpenAccess, Licencja_OpenAccess, Wersja_Tekstu_OpenAccess
from bpp.models.struktura import Jednostka_Wydzial
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor
from bpp.models.zrodlo import Redakcja_Zrodla

class JezykAdmin(RestrictDeletionToAdministracjaGroupAdmin):
    list_display = ['nazwa', 'skrot', 'skrot_dla_pbn']


admin.site.register(Jezyk, JezykAdmin)
admin.site.register(Funkcja_Autora, RestrictDeletionToAdministracjaGroupAdmin)
admin.site.register(Rodzaj_Zrodla, RestrictDeletionToAdministracjaGroupAdmin)
admin.site.register(Status_Korekty, RestrictDeletionToAdministracjaGroupAdmin)
admin.site.register(Zrodlo_Informacji, RestrictDeletionToAdministracjaGroupAdmin)

admin.site.register(OrganPrzyznajacyNagrody,
                    RestrictDeletionToAdministracjaGroupAdmin)


class Charakter_PBNAdmin(RestrictDeletionToAdministracjaGroupMixin,
                         CommitedModelAdmin):
    list_display = ['identyfikator', 'wlasciwy_dla', 'opis',
                    'charaktery_formalne',
                    'typy_kbn']
    readonly_fields = ['identyfikator', 'wlasciwy_dla', 'opis', 'help_text']

    def charaktery_formalne(self, rec):
        return ", ".join(["%s (%s)" % (x.nazwa, x.skrot)for x in
                          rec.charakter_formalny_set.all()])

    def typy_kbn(self, rec):
        return ", ".join(["%s (%s)" % (x.nazwa, x.skrot) for x in
                                       rec.typ_kbn_set.all()])

admin.site.register(Charakter_PBN, Charakter_PBNAdmin)


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
    list_display = ['nazwa', 'skrot', 'artykul_pbn', 'charakter_pbn']

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


# Autor_Jednostka

class Autor_JednostkaInlineForm(forms.ModelForm):
    autor = forms.ModelChoiceField(
        queryset=Autor.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='bpp:autor-autocomplete')
    )

    jednostka = forms.ModelChoiceField(
        queryset=Jednostka.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='bpp:jednostka-autocomplete')
    )

    class Meta:
        fields = "__all__"

class Autor_JednostkaInline(admin.TabularInline):
    model = Autor_Jednostka
    form = Autor_JednostkaInlineForm
    extra = 1

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

    list_display = ['nazwisko',
                    'imiona',
                    'tytul',
                    'poprzednie_nazwiska',
                    'email',
                    'pbn_id',
                    'orcid']
    list_select_related = ['tytul',]
    fields = None
    inlines = [Autor_JednostkaInline, ]
    list_filter = [JednostkaFilter,
                   'aktualna_jednostka__wydzial',
                   'tytul',
                   PBNIDObecnyFilter,
                   OrcidObecnyFilter,
                   PeselMD5ObecnyFilter]
    search_fields = ['imiona', 'nazwisko', 'poprzednie_nazwiska', 'email', 'www', 'id', 'pbn_id']
    readonly_fields = ('pesel_md5', 'ostatnio_zmieniony')

    fieldsets = (
        (None, {
            'fields': (
                'imiona', 'nazwisko', 'tytul', 'pokazuj',
                'email', 'www', 'orcid', 'pbn_id', 'pesel_md5')
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



class Redakcja_ZrodlaForm(forms.ModelForm):
    redaktor = forms.ModelChoiceField(
        queryset=Autor.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='bpp:autor-autocomplete')
    )

    model = Redakcja_Zrodla


class Redakcja_ZrodlaInline(admin.TabularInline):
    model = Redakcja_Zrodla
    extra = 1
    form = Redakcja_ZrodlaForm
    class Meta:
        fields = "__all__"


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


class Patent_Admin(AdnotacjeZDatamiMixin, Wydawnictwo_ZwarteAdmin_Baza):
    inlines = (generuj_inline_dla_autorow(Patent_Autor),)

    list_display = ['tytul_oryginalny', 'ostatnio_zmieniony']

    search_fields = [
        'tytul_oryginalny', 'szczegoly', 'uwagi', 'informacje',
        'slowa_kluczowe', 'rok', 'adnotacje', 'id', ]

    list_filter = ['status_korekty', 'recenzowana', ]

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
