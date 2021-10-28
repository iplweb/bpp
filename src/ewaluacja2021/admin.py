# Register your models here.

from ewaluacja2021.models import IloscUdzialowDlaAutora

from django.contrib import admin


@admin.register(IloscUdzialowDlaAutora)
class IloscUdzialowDlaAutoraAdmin(admin.ModelAdmin):
    list_display = [
        "autor",
        "dyscyplina_naukowa",
        "ilosc_udzialow",
        "ilosc_udzialow_monografie",
    ]
    list_select_related = ["autor", "autor__tytul", "dyscyplina_naukowa"]
    search_fields = [
        "autor__nazwisko",
        "dyscyplina_naukowa__kod",
        "dyscyplina_naukowa__nazwa",
    ]
    list_filter = ["dyscyplina_naukowa"]
    ordering = ("autor__nazwisko", "autor__imiona", "dyscyplina_naukowa__nazwa")
