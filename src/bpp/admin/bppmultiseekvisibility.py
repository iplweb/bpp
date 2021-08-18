from django.contrib import admin

from bpp.models import BppMultiseekVisibility


@admin.register(BppMultiseekVisibility)
class BppMulitiseekVisibilityAdmin(admin.ModelAdmin):
    list_display = ["label", "public", "authenticated", "staff"]
    list_filter = ["public", "authenticated", "staff"]
    readonly_fields = ["label", "field_name", "sort_order"]
    fields = ["label", "field_name", "public", "authenticated", "staff"]
    search_fields = ["label", "field_name"]
