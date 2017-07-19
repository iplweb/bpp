# -*- encoding: utf-8 -*-
from django.contrib import admin

from bpp.admin.common import CommitedModelAdmin
from bpp.models.seria import Seria_Wydawnicza


class Seria_WydawniczaAdmin(CommitedModelAdmin):
    list_display = ['nazwa', 'issn']
    search_fields = ['nazwa', 'issn']


admin.site.register(Seria_Wydawnicza, Seria_WydawniczaAdmin)
