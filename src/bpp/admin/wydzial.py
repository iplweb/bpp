from adminsortable2.admin import SortableAdminMixin
from django.contrib import admin

from ..models import Wydzial  # Publikacja_Habilitacyjna
from .core import BaseBppAdminMixin, RestrictDeletionToAdministracjaGroupMixin
from .helpers.fieldsets import ADNOTACJE_FIELDSET
from .helpers.mixins import ZapiszZAdnotacjaMixin
from .helpers.site_filtered import SiteFilteredAdminMixin
from .xlsx_export import resources
from .xlsx_export.mixins import EksportDanychMixin


class WydzialAdmin(
    SiteFilteredAdminMixin,
    RestrictDeletionToAdministracjaGroupMixin,
    ZapiszZAdnotacjaMixin,
    EksportDanychMixin,
    SortableAdminMixin,
    BaseBppAdminMixin,
    admin.ModelAdmin,
):
    uczelnia_field_path = "uczelnia"
    change_list_template = "adminsortable2/change_list.html"
    resource_classes = [resources.WydzialResource]

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
                    "pokazuj_opis",
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
