from rest_framework.permissions import BasePermission

from bpp.const import GR_RAPORTY_WYSWIETLANIE


class IsGrupaRaportyWyswietlanie(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_superuser or (
            GR_RAPORTY_WYSWIETLANIE
            in request.user.groups.values_list("name", flat=True)
        )
