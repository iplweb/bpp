from django.contrib import admin

from bpp.admin.core import BaseBppAdmin
from bpp.models import Autor_Dyscyplina


class Autor_DyscyplinaAdmin(BaseBppAdmin):
    list_filter = [
        "rok",
        "dyscyplina_naukowa",
        "subdyscyplina_naukowa",
        "rodzaj_autora",
        "wymiar_etatu",
    ]
    list_display = [
        "autor",
        "rok",
        "rodzaj_autora",
        "wymiar_etatu",
        "dyscyplina_naukowa",
        "procent_dyscypliny",
        "subdyscyplina_naukowa",
        "procent_subdyscypliny",
    ]
    ordering = ("autor", "rok")


admin.site.register(Autor_Dyscyplina, Autor_DyscyplinaAdmin)
