from rest_framework.permissions import BasePermission

from bpp.const import GR_RAPORTY_WYSWIETLANIE
from bpp.views.zapytanie import user_can_use_query_editor


class IsGrupaRaportyWyswietlanie(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_superuser or (
            GR_RAPORTY_WYSWIETLANIE
            in request.user.groups.values_list("name", flat=True)
        )


class MoznaUzywacZapytania(BasePermission):
    """Dostęp do DjangoQL po API = ten sam kontrakt co web-edytor:
    superuser albo staff w grupie „wprowadzanie danych"."""

    message = (
        "Wymagane konto redaktora (staff w grupie 'wprowadzanie danych') "
        "lub superusera."
    )

    def has_permission(self, request, view):
        return user_can_use_query_editor(request.user)
