from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import IgnoredSource, NotADuplicate


@admin.register(NotADuplicate)
class NotADuplicateAdmin(admin.ModelAdmin):
    list_display = ["id", "zrodlo_link", "duplikat_link", "created_by", "created_on"]
    list_filter = ["created_on", "created_by"]
    search_fields = ["zrodlo__nazwa", "duplikat__nazwa"]
    readonly_fields = ["zrodlo", "duplikat", "created_by", "created_on"]
    date_hierarchy = "created_on"

    def zrodlo_link(self, obj):
        if obj.zrodlo:
            url = reverse("admin:bpp_zrodlo_change", args=[obj.zrodlo.pk])
            return format_html('<a href="{}">{}</a>', url, obj.zrodlo.nazwa)
        return "-"

    zrodlo_link.short_description = "Źródło"

    def duplikat_link(self, obj):
        if obj.duplikat:
            url = reverse("admin:bpp_zrodlo_change", args=[obj.duplikat.pk])
            return format_html('<a href="{}">{}</a>', url, obj.duplikat.nazwa)
        return "-"

    duplikat_link.short_description = "Duplikat"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(IgnoredSource)
class IgnoredSourceAdmin(admin.ModelAdmin):
    list_display = ["id", "zrodlo_link", "reason_short", "created_by", "created_on"]
    list_filter = ["created_on", "created_by"]
    search_fields = ["zrodlo__nazwa", "reason"]
    readonly_fields = ["zrodlo", "created_by", "created_on"]
    date_hierarchy = "created_on"

    def zrodlo_link(self, obj):
        if obj.zrodlo:
            url = reverse("admin:bpp_zrodlo_change", args=[obj.zrodlo.pk])
            return format_html('<a href="{}">{}</a>', url, obj.zrodlo.nazwa)
        return "-"

    zrodlo_link.short_description = "Źródło"

    def reason_short(self, obj):
        if obj.reason:
            return obj.reason[:50] + "..." if len(obj.reason) > 50 else obj.reason
        return "-"

    reason_short.short_description = "Powód"

    def has_add_permission(self, request):
        return False
