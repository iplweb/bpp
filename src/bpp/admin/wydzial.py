# -*- encoding: utf-8 -*-

# -*- encoding: utf-8 -*-
from adminsortable2.admin import SortableAdminMixin
from django.contrib import admin

from .core import CommitedModelAdmin
from .core import RestrictDeletionToAdministracjaGroupMixin
from .helpers import *
from ..models import Wydzial  # Publikacja_Habilitacyjna


class WydzialAdmin(
    RestrictDeletionToAdministracjaGroupMixin,
    SortableAdminMixin,
    ZapiszZAdnotacjaMixin,
    CommitedModelAdmin,
):
    list_display = [
        "nazwa",
        "skrot",
        "kolejnosc",
        "widoczny",
        "ranking_autorow",
        "zarzadzaj_automatycznie",
        "otwarcie",
        "zamkniecie",
        "pbn_id",
    ]
    list_filter = [
        "uczelnia",
        "zezwalaj_na_ranking_autorow",
        "widoczny",
        "zarzadzaj_automatycznie",
    ]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "uczelnia",
                    "nazwa",
                    "skrot_nazwy",
                    "skrot",
                    "pbn_id",
                    "opis",
                    "widoczny",
                    "zezwalaj_na_ranking_autorow",
                    "zarzadzaj_automatycznie",
                    "otwarcie",
                    "zamkniecie",
                ),
            },
        ),
        ADNOTACJE_FIELDSET,
    )

    def ranking_autorow(self, obj):
        return obj.zezwalaj_na_ranking_autorow

    ranking_autorow.short_description = "Ranking autorów"
    ranking_autorow.boolean = True
    ranking_autorow.admin_order_field = "zezwalaj_na_ranking_autorow"


admin.site.register(Wydzial, WydzialAdmin)
