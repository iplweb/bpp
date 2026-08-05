from django.contrib import admin

from ..models import Kierunek_Studiow
from .core import BaseBppAdminMixin, RestrictDeletionToAdministracjaGroupMixin


@admin.register(Kierunek_Studiow)
class Kierunek_StudiowAdmin(
    RestrictDeletionToAdministracjaGroupMixin, BaseBppAdminMixin, admin.ModelAdmin
):
    list_display_links = ["nazwa"]
    list_display = ["nazwa", "skrot", "wydzial"]
    search_fields = ["nazwa", "skrot", "wydzial__nazwa"]
    fields = ["nazwa", "skrot", "wydzial", "opis", "adnotacje"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "wydzial":
            from bpp.models import Jednostka

            kwargs["queryset"] = Jednostka.objects.filter(parent__isnull=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
