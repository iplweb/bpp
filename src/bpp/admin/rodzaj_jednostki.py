from django.contrib import admin

from bpp.models import RodzajJednostki


class RodzajJednostkiAdmin(admin.ModelAdmin):
    list_display = [
        "nazwa",
        "skrot",
        "kolejnosc",
        "wyklucz_z_rankingu_autorow",
        "pokazuj_jako_odrebna_sekcje",
    ]
    list_editable = ["kolejnosc"]
    search_fields = ["nazwa", "skrot"]


admin.site.register(RodzajJednostki, RodzajJednostkiAdmin)
