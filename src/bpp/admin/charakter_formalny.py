from mptt.admin import DraggableMPTTAdmin

from ..models import Charakter_Formalny  # Publikacja_Habilitacyjna
from .core import BaseBppAdminMixin, RestrictDeletionToAdministracjaGroupMixin

from django.contrib import admin


# Proste tabele
class Charakter_FormalnyAdmin(
    RestrictDeletionToAdministracjaGroupMixin, BaseBppAdminMixin, DraggableMPTTAdmin
):
    list_display_links = ["nazwa"]
    list_display = [
        "tree_actions",
        "nazwa",
        "skrot",
        "publikacja",
        "streszczenie",
        "nazwa_w_primo",
        "charakter_pbn",
        "charakter_sloty",
        "rodzaj_pbn",
    ]
    list_filter = (
        "publikacja",
        "streszczenie",
        "nazwa_w_primo",
        "charakter_pbn",
        "rodzaj_pbn",
    )
    search_fields = ["skrot", "nazwa"]

    change_list_template = "admin/grappelli_mptt_change_list.html"


admin.site.register(Charakter_Formalny, Charakter_FormalnyAdmin)
