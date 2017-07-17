# -*- encoding: utf-8 -*-
from dal.forms import FutureModelForm
from dal_queryset_sequence.fields import QuerySetSequenceModelField
from dal_select2_queryset_sequence.widgets import \
    QuerySetSequenceSelect2
from queryset_sequence import QuerySetSequence

from bpp.jezyk_polski import warianty_zapisanego_nazwiska
from bpp.models.praca_habilitacyjna import Publikacja_Habilitacyjna

from dal import autocomplete

from django import forms
from django.contrib import admin
from django.forms.widgets import HiddenInput



from django.contrib.auth.forms import UserCreationForm
from django.db.models.fields import BLANK_CHOICE_DASH
from django.utils.safestring import mark_safe
from multiseek.models import SearchForm

from bpp.admin.filters import LiczbaZnakowFilter, CalkowitaLiczbaAutorowFilter, \
    JednostkaFilter, PBNIDObecnyFilter, \
    PeselMD5ObecnyFilter, OrcidObecnyFilter
from bpp.admin.helpers import *
from bpp.models import Jezyk, Typ_KBN, Uczelnia, Wydzial, \
    Jednostka, Tytul, Autor, Autor_Jednostka, Funkcja_Autora, Rodzaj_Zrodla, \
    Zrodlo, Punktacja_Zrodla, Typ_Odpowiedzialnosci, Status_Korekty, \
    Zrodlo_Informacji, Wydawnictwo_Ciagle, Charakter_Formalny, \
    Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor, Praca_Doktorska, \
    Praca_Habilitacyjna, Patent, Patent_Autor, BppUser # Publikacja_Habilitacyjna

from .common import BaseBppAdmin, CommitedModelAdmin, \
    KolumnyZeSkrotamiMixin, generuj_inline_dla_autorow
from .wydawnictwo_zwarte import Wydawnictwo_ZwarteAdmin_Baza, Wydawnictwo_ZwarteAdmin
from .konferencja import KonferencjaAdmin

# Proste tabele
from bpp.models.openaccess import Tryb_OpenAccess_Wydawnictwo_Ciagle, Tryb_OpenAccess_Wydawnictwo_Zwarte, \
    Czas_Udostepnienia_OpenAccess, Licencja_OpenAccess, Wersja_Tekstu_OpenAccess
from bpp.models.struktura import Jednostka_Wydzial
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor
from bpp.models.zrodlo import Redakcja_Zrodla

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
                'nazwa',
                'nazwa_dopelniacz_field',
                'skrot',
                'pbn_id',
                'logo_www',
                'logo_svg',
                'favicon_ico',
                'obca_jednostka',
                'pokazuj_punktacje_wewnetrzna',
                'pokazuj_index_copernicus'),
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
                'uczelnia', 'nazwa', 'skrot_nazwy', 'skrot', 'pbn_id',
                'opis', 'kolejnosc', 'widoczny',
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
                'imiona', 'nazwisko', 'tytul', 'pokazuj_na_stronach_jednostek',
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


#
# Wydaniwcto Ciągłe
#


# Widget do automatycznego uzupełniania punktacji wydawnictwa ciągłego

class Button(forms.Widget):
    """
    A widget that handles a submit button.
    """

    def render(self, name, value, attrs=None):
        final_attrs = self.build_attrs(
                self.attrs,
                type="button",
                name=name)

        return mark_safe('<input type="button"%s value="%s" />' % (
            forms.widgets.flatatt(final_attrs),
            final_attrs['label'],
        ))



class Wydawnictwo_Ciagle_Form(forms.ModelForm):
    zrodlo = forms.ModelChoiceField(
        queryset=Zrodlo.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='bpp:zrodlo-autocomplete')
    )

    uzupelnij_punktacje = forms.CharField(
        initial=None,
        max_length=50,
        required=False,
        label="Uzupełnij punktację",
        widget=Button(dict(
            id='id_uzupelnij_punktacje',
            label="Uzupełnij punktację",
        ))
    )

    class Meta:
        fields = "__all__"

        widgets = {
            'strony': forms.TextInput(attrs=dict(style="width: 150px")),
            'tom': forms.TextInput(attrs=dict(style="width: 150px")),
            'nr_zeszytu': forms.TextInput(attrs=dict(style="width: 150px"))
        }


class Wydawnictwo_CiagleAdmin(KolumnyZeSkrotamiMixin, AdnotacjeZDatamiOrazPBNMixin, CommitedModelAdmin):
    formfield_overrides = NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW

    form = Wydawnictwo_Ciagle_Form

    list_display = ['tytul_oryginalny', 'zrodlo_col', 'rok',
                    'typ_kbn__skrot', 'charakter_formalny__skrot',
                    'liczba_znakow_wydawniczych',
                    'ostatnio_zmieniony']

    list_select_related = ['zrodlo', 'typ_kbn', 'charakter_formalny']

    search_fields = [
        'tytul', 'tytul_oryginalny', 'szczegoly', 'uwagi', 'informacje',
        'slowa_kluczowe', 'rok', 'id',
        'issn', 'e_issn', 'zrodlo__nazwa', 'zrodlo__skrot', 'adnotacje',
        'liczba_znakow_wydawniczych'
    ]

    list_filter = ['status_korekty', 'afiliowana', 'recenzowana', 'typ_kbn',
                   'charakter_formalny', 'jezyk', LiczbaZnakowFilter, 'rok']

    fieldsets = (
        ('Wydawnictwo ciągłe', {
            'fields':
                DWA_TYTULY
                + ('zrodlo',)
                + MODEL_ZE_SZCZEGOLAMI
                + ('nr_zeszytu', )
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


class Praca_DoktorskaForm(forms.ModelForm):
    autor = forms.ModelChoiceField(
        queryset=Autor.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='bpp:autor-z-uczelni-autocomplete')
    )

    jednostka = forms.ModelChoiceField(
        queryset=Jednostka.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='bpp:jednostka-autocomplete')
    )

    promotor = forms.ModelChoiceField(
        queryset=Autor.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='bpp:autor-z-uczelni-autocomplete')
    )

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
class Publikacja_HabilitacyjnaForm(FutureModelForm):
    publikacja = QuerySetSequenceModelField(
        queryset=QuerySetSequence(
            Wydawnictwo_Zwarte.objects.all(),
            Wydawnictwo_Ciagle.objects.all(),
            Patent.objects.all()
        ),
        required=True,
        widget=QuerySetSequenceSelect2(
            'bpp:podrzedna-publikacja-habilitacyjna-autocomplete',
            forward=['autor'],
            attrs=dict(style="width: 764px;")
        ),
    )

    class Meta:
        model = Publikacja_Habilitacyjna
        widgets = {'kolejnosc': HiddenInput}
        fields = ['publikacja', 'kolejnosc']


class Publikacja_Habilitacyjna_Inline(admin.TabularInline):
    model = Publikacja_Habilitacyjna
    form = Publikacja_HabilitacyjnaForm
    extra = 1
    sortable_field_name = "kolejnosc"


class Praca_HabilitacyjnaForm(forms.ModelForm):
    autor = forms.ModelChoiceField(
        queryset=Autor.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='bpp:autor-z-uczelni-autocomplete')
    )

    jednostka = forms.ModelChoiceField(
        queryset=Jednostka.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='bpp:jednostka-autocomplete')
    )

    class Meta:
        fields = "__all__"

class Praca_HabilitacyjnaAdmin(Praca_Doktorska_Habilitacyjna_Admin_Base):
    inlines = [Publikacja_Habilitacyjna_Inline, ]

    form = Praca_HabilitacyjnaForm

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
