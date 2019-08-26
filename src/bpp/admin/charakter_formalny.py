from django.contrib import admin
from mptt.admin import MPTTModelAdmin

from .core import CommitedModelAdmin
from .core import RestrictDeletionToAdministracjaGroupMixin
from ..models import Charakter_Formalny  # Publikacja_Habilitacyjna


# Proste tabele
class Charakter_FormalnyAdmin(RestrictDeletionToAdministracjaGroupMixin, CommitedModelAdmin, MPTTModelAdmin):
    list_display = ['nazwa', 'skrot', 'publikacja', 'streszczenie', 'nazwa_w_primo',
                    'charakter_pbn', 'charakter_sloty', 'rodzaj_pbn']
    list_filter = ('publikacja', 'streszczenie', 'nazwa_w_primo', 'charakter_pbn',
                   'rodzaj_pbn',)
    search_fields = ['skrot', 'nazwa']

    change_list_template = 'admin/grappelli_mptt_change_list.html'


admin.site.register(Charakter_Formalny, Charakter_FormalnyAdmin)
