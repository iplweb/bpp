from ..models import Crossref_Mapper
from .core import BaseBppAdminMixin

from django.contrib import admin


@admin.register(Crossref_Mapper)
class Crossref_Mapper_Admin(BaseBppAdminMixin, admin.ModelAdmin):
    list_display = ["charakter_crossref", "charakter_formalny_bpp"]
    list_select_related = ["charakter_formalny_bpp"]

    list_filter = ("charakter_crossref", "charakter_formalny_bpp")
    search_fields = ["charakter_formalny_bpp__nazwa", "charakter_formalny_bpp__skrot"]
