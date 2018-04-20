# -*- encoding: utf-8 -*-

# -*- encoding: utf-8 -*-

from django.contrib import admin

from .core import CommitedModelAdmin
from .core import RestrictDeletionToAdministracjaGroupMixin
from .helpers import *
from ..models import Wydzial  # Publikacja_Habilitacyjna
from ..models.struktura import Jednostka, Jednostka_Wydzial


# Wydział

class WydzialAdmin(RestrictDeletionToAdministracjaGroupMixin,
                   ZapiszZAdnotacjaMixin, CommitedModelAdmin):
    list_display = ['nazwa', 'skrot', 'uczelnia', 'kolejnosc', 'widoczny',
                    'ranking_autorow',
                    'zarzadzaj_automatycznie', 'otwarcie', 'zamkniecie',
                    'pbn_id']
    list_filter = ['uczelnia', 'zezwalaj_na_ranking_autorow', 'widoczny',
                   'zarzadzaj_automatycznie', ]
    fieldsets = (
        (None, {
            'fields': (
                'uczelnia', 'nazwa', 'skrot_nazwy', 'skrot', 'pbn_id',
                'opis', 'kolejnosc', 'widoczny',
                'zezwalaj_na_ranking_autorow', 'zarzadzaj_automatycznie',
                'otwarcie', 'zamkniecie'),
        }),
        ADNOTACJE_FIELDSET
    )

    def ranking_autorow(self, obj):
        return obj.zezwalaj_na_ranking_autorow

    ranking_autorow.short_description = "Ranking autorów"
    ranking_autorow.boolean = True
    ranking_autorow.admin_order_field = 'zezwalaj_na_ranking_autorow'


admin.site.register(Wydzial, WydzialAdmin)


# Jednostka

class Jednostka_WydzialInline(admin.TabularInline):
    model = Jednostka_Wydzial
    extra = 1


class JednostkaAdmin(RestrictDeletionToAdministracjaGroupMixin, ZapiszZAdnotacjaMixin, CommitedModelAdmin):
    list_display = ('nazwa', 'skrot', 'wydzial', 'widoczna',
                    'wchodzi_do_raportow', 'skupia_pracownikow', 'zarzadzaj_automatycznie', 'pbn_id')
    list_select_related = ['wydzial', ]
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
