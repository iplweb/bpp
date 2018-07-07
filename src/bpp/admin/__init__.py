# -*- encoding: utf-8 -*-

from dal import autocomplete
from django.contrib import admin
from django.contrib.auth.forms import UserCreationForm
from multiseek.models import SearchForm

from bpp.models import Rodzaj_Prawa_Patentowego, Zewnetrzna_Baza_Danych
# Proste tabele
from bpp.models.openaccess import Tryb_OpenAccess_Wydawnictwo_Ciagle, Tryb_OpenAccess_Wydawnictwo_Zwarte, \
    Czas_Udostepnienia_OpenAccess, Licencja_OpenAccess, Wersja_Tekstu_OpenAccess
from bpp.models.zrodlo import Redakcja_Zrodla
from .autor import AutorAdmin  # noqa
from .core import BaseBppAdmin, CommitedModelAdmin, \
    KolumnyZeSkrotamiMixin, generuj_inline_dla_autorow
from .core import RestrictDeletionToAdministracjaGroupAdmin, \
    RestrictDeletionToAdministracjaGroupMixin
from .dyscyplina_naukowa import Dyscyplina_NaukowaAdmin  # noqa
from .filters import LiczbaZnakowFilter, CalkowitaLiczbaAutorowFilter, \
    JednostkaFilter, PBNIDObecnyFilter, \
    PeselMD5ObecnyFilter, OrcidObecnyFilter
from .helpers import *
from .jednostka import JednostkaAdmin  # NOQA
from .konferencja import KonferencjaAdmin  # noqa
from .patent import Patent_Admin  # noqa
from .praca_doktorska import Praca_DoktorskaAdmin  # noqa
from .praca_habilitacyjna import Praca_HabilitacyjnaAdmin  # noqa
from .seria_wydawnicza import Seria_WydawniczaAdmin
from .uczelnia import UczelniaAdmin  # NOQA
from .charakter_formalny import Charakter_FormalnyAdmin  # noqa
from .wydawnictwo_ciagle import Wydawnictwo_CiagleAdmin
from .wydawnictwo_zwarte import Wydawnictwo_ZwarteAdmin_Baza, Wydawnictwo_ZwarteAdmin
from .wydzial import WydzialAdmin
from ..models import Jezyk, Typ_KBN, Tytul, Autor, Funkcja_Autora, Rodzaj_Zrodla, \
    Zrodlo, Punktacja_Zrodla, Typ_Odpowiedzialnosci, Status_Korekty, \
    Zrodlo_Informacji, BppUser  # Publikacja_Habilitacyjna
from ..models.nagroda import OrganPrzyznajacyNagrody
from ..models.system import Charakter_PBN


class JezykAdmin(RestrictDeletionToAdministracjaGroupAdmin):
    list_display = ['nazwa', 'skrot', 'skrot_dla_pbn']


admin.site.register(Jezyk, JezykAdmin)
admin.site.register(Funkcja_Autora, RestrictDeletionToAdministracjaGroupAdmin)
admin.site.register(Rodzaj_Zrodla, RestrictDeletionToAdministracjaGroupAdmin)
admin.site.register(Status_Korekty, RestrictDeletionToAdministracjaGroupAdmin)
admin.site.register(Zrodlo_Informacji, RestrictDeletionToAdministracjaGroupAdmin)
admin.site.register(Rodzaj_Prawa_Patentowego, RestrictDeletionToAdministracjaGroupAdmin)

admin.site.register(OrganPrzyznajacyNagrody,
                    RestrictDeletionToAdministracjaGroupAdmin)


@admin.register(Zewnetrzna_Baza_Danych)
class Zewnetrzna_Baza_DanychAdmin(RestrictDeletionToAdministracjaGroupAdmin, CommitedModelAdmin):
    list_display = ['nazwa', 'skrot']


class Charakter_PBNAdmin(RestrictDeletionToAdministracjaGroupMixin,
                         CommitedModelAdmin):
    list_display = ['identyfikator', 'wlasciwy_dla', 'opis',
                    'charaktery_formalne',
                    'typy_kbn']
    readonly_fields = ['identyfikator', 'wlasciwy_dla', 'opis', 'help_text']

    def charaktery_formalne(self, rec):
        return ", ".join(["%s (%s)" % (x.nazwa, x.skrot) for x in
                          rec.charakter_formalny_set.all()])

    def typy_kbn(self, rec):
        return ", ".join(["%s (%s)" % (x.nazwa, x.skrot) for x in
                          rec.typ_kbn_set.all()])


admin.site.register(Charakter_PBN, Charakter_PBNAdmin)


class NazwaISkrotAdmin(RestrictDeletionToAdministracjaGroupMixin, CommitedModelAdmin):
    list_display = ['skrot', 'nazwa']
    search_fields = ['skrot', 'nazwa']


admin.site.register(Tytul, NazwaISkrotAdmin)


class Typ_KBNAdmin(RestrictDeletionToAdministracjaGroupAdmin, CommitedModelAdmin):
    list_display = ['nazwa', 'skrot', 'artykul_pbn', 'charakter_pbn']


admin.site.register(Typ_KBN, Typ_KBNAdmin)


class Typ_OdpowiedzialnosciAdmin(RestrictDeletionToAdministracjaGroupMixin, CommitedModelAdmin):
    list_display = ['nazwa', 'skrot', 'typ_ogolny']


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
