from adminsortable2.admin import SortableAdminMixin

from django.contrib import admin

from bpp.models import BppMultiseekVisibility


@admin.register(BppMultiseekVisibility)
class BppMulitiseekVisibilityAdmin(SortableAdminMixin, admin.ModelAdmin):
    list_display = ["label", "public", "authenticated", "staff", "sort_order"]
    list_filter = ["public", "authenticated", "staff"]
    readonly_fields = ["label", "field_name", "sort_order"]
    fields = ["label", "field_name", "public", "authenticated", "staff"]
    search_fields = ["label", "field_name"]

    list_per_page = 150

    def has_add_permission(self, request):
        return False
