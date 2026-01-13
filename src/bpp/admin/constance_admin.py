"""
Dostosowanie panelu administracyjnego django-constance dla BPP.

Ogranicza dostęp do ustawień constance wyłącznie dla superużytkowników.
"""

from constance.admin import Config, ConstanceAdmin
from django.contrib import admin


class BppConstanceAdmin(ConstanceAdmin):
    """Ogranicza dostęp do ustawień Constance wyłącznie dla superużytkowników."""

    def has_module_permission(self, request):
        """Tylko superużytkownicy mogą widzieć moduł w panelu admin."""
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        """Tylko superużytkownicy mogą przeglądać ustawienia."""
        return request.user.is_active and request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        """Tylko superużytkownicy mogą zmieniać ustawienia."""
        return request.user.is_active and request.user.is_superuser


admin.site.unregister([Config])
admin.site.register([Config], BppConstanceAdmin)
