from ..models import Kierunek_Studiow
from .core import BaseBppAdminMixin, RestrictDeletionToAdministracjaGroupMixin

from django.contrib import admin


@admin.register(Kierunek_Studiow)
class Kierunek_StudiowAdmin(
    RestrictDeletionToAdministracjaGroupMixin, BaseBppAdminMixin, admin.ModelAdmin
):
    list_display_links = ["nazwa"]
    list_display = ["nazwa", "skrot", "wydzial"]
    search_fields = ["nazwa", "skrot", "wydzial__nazwa"]
    fields = ["nazwa", "skrot", "wydzial", "opis", "adnotacje"]
