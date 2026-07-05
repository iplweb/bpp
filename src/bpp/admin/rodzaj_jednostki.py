from adminsortable2.admin import SortableAdminMixin
from django.contrib import admin

from bpp.models import RodzajJednostki


class RodzajJednostkiAdmin(SortableAdminMixin, admin.ModelAdmin):
    # Kolejność ustawiana przeciąganiem (adminsortable2) po polu ``kolejnosc``
    # (Meta.ordering) — dlatego ``kolejnosc`` znika z list_display/list_editable.
    list_display = [
        "nazwa",
        "skrot",
        "wyklucz_z_rankingu_autorow",
        "pokazuj_jako_odrebna_sekcje",
        "pokazuj_strukture_podjednostek",
    ]
    search_fields = ["nazwa", "skrot"]


admin.site.register(RodzajJednostki, RodzajJednostkiAdmin)
