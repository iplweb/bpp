from django.contrib import admin

from bpp.admin.core import DynamicAdminFilterMixin

from .models import MenuClick


@admin.register(MenuClick)
class MenuClickAdmin(DynamicAdminFilterMixin, admin.ModelAdmin):
    list_display = ["user", "menu_label", "clicked_at"]
    list_filter = ["user", "menu_label", "clicked_at"]
    search_fields = ["user__username", "menu_label", "menu_url"]
    readonly_fields = ["user", "menu_label", "menu_url", "clicked_at"]
    date_hierarchy = "clicked_at"
    ordering = ["-clicked_at"]

    def has_add_permission(self, request):
        # Kliknięcia są dodawane tylko przez system
        return False

    def has_change_permission(self, request, obj=None):
        # Kliknięcia są tylko do odczytu
        return False
