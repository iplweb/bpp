# -*- encoding: utf-8 -*-

# -*- encoding: utf-8 -*-
from django.contrib import admin

from bpp.models import Autor_Jednostka
from miniblog.admin import SmallerTextarea
from .core import CommitedModelAdmin
from .core import RestrictDeletionToAdministracjaGroupMixin
from .helpers import *
from ..models.struktura import Jednostka, Jednostka_Wydzial


class Jednostka_WydzialInline(admin.TabularInline):
    model = Jednostka_Wydzial
    extra = 1


class Autor_JednostkaForm(forms.ModelForm):
    model = Autor_Jednostka

    class Meta:
        fields = ['autor', 'rozpoczal_prace', 'zakonczyl_prace', 'funkcja']


class Autor_JednostkaInline(admin.TabularInline):
    form = Autor_JednostkaForm
    model = Autor_Jednostka
    readonly_fields = ['autor']
    formset = LimitingFormset
    extra = 0


class JednostkaAdmin(RestrictDeletionToAdministracjaGroupMixin, ZapiszZAdnotacjaMixin, CommitedModelAdmin):
    list_display = ('nazwa', 'skrot', 'wydzial', 'widoczna',
                    'wchodzi_do_raportow', 'skupia_pracownikow', 'zarzadzaj_automatycznie', 'pbn_id')
    list_select_related = ['wydzial', ]
    fields = None
    list_filter = ('wydzial', 'widoczna', 'wchodzi_do_raportow', 'skupia_pracownikow', 'zarzadzaj_automatycznie')
    search_fields = ['nazwa', 'skrot', 'wydzial__nazwa']

    inlines = (Jednostka_WydzialInline,
               Autor_JednostkaInline,
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
