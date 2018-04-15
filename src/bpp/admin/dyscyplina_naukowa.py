# -*- encoding: utf-8 -*-

# -*- encoding: utf-8 -*-

from django.contrib import admin
from mptt.admin import MPTTModelAdmin

from bpp.models import Dyscyplina_Naukowa
from .core import CommitedModelAdmin
from .core import RestrictDeletionToAdministracjaGroupMixin
from .helpers import *


class Dyscyplina_NaukowaAdmin(RestrictDeletionToAdministracjaGroupMixin, MPTTModelAdmin):
    list_display = ( 'nazwa', 'kod', 'widoczna')  # Sane defaults.

    fields = None
    search_fields = ('nazwa', 'kod',)
    list_filter = ('widoczna',)

    fields = ["nazwa", "kod", "widoczna", "dyscyplina_nadrzedna"]
    mptt_level_indent = 40


admin.site.register(Dyscyplina_Naukowa, Dyscyplina_NaukowaAdmin)
