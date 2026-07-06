from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    IgnoredSource,
    NotADuplicate,
    ScanZrodelForDuplicates,
    SourceDuplicateCandidate,
)


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


@admin.register(ScanZrodelForDuplicates)
class ScanZrodelForDuplicatesAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "state_display",
        "owner",
        "created_on",
        "finished_on",
        "total_sources",
        "sources_scanned",
        "duplicates_found",
    ]
    list_filter = ["finished_successfully", "cancelled", "created_on"]
    date_hierarchy = "created_on"
    readonly_fields = [
        "owner",
        "created_on",
        "started_on",
        "finished_on",
        "finished_successfully",
        "cancelled",
        "cancel_requested",
        "total_sources",
        "sources_scanned",
        "duplicates_found",
        "traceback",
        "result_context",
    ]
    actions = ["force_cancel"]

    def state_display(self, obj):
        # Emoji zamiast Foundation Icons (reguła: admin używa emoji).
        icon = {
            "NOT_STARTED": "⏳",
            "STARTED": "🔄",
            "FINISHED_OK": "✅",
            "FINISHED_ERROR": "❌",
            "CANCELLED": "🚫",
        }.get(obj.get_state(), "❔")
        return f"{icon} {obj.get_state()}"

    state_display.short_description = "Stan"

    @admin.action(description="🚫 Oznacz jako anulowane (osierocone skany)")
    def force_cancel(self, request, queryset):
        updated = queryset.filter(finished_on__isnull=True).update(
            cancelled=True, finished_on=timezone.now()
        )
        self.message_user(request, f"Anulowano {updated} skanowań.")

    def has_add_permission(self, request):
        return False


@admin.register(SourceDuplicateCandidate)
class SourceDuplicateCandidateAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "main_zrodlo_link",
        "duplicate_zrodlo_link",
        "confidence_score",
        "status",
        "scan",
    ]
    list_filter = ["status", "scan"]
    search_fields = ["main_nazwa", "duplicate_nazwa"]
    readonly_fields = [
        "scan",
        "main_zrodlo",
        "duplicate_zrodlo",
        "confidence_score",
        "main_nazwa",
        "duplicate_nazwa",
        "main_pub_count",
        "duplicate_pub_count",
        "created_at",
    ]

    def main_zrodlo_link(self, obj):
        if obj.main_zrodlo_id:
            url = reverse("admin:bpp_zrodlo_change", args=[obj.main_zrodlo_id])
            return format_html('<a href="{}">{}</a>', url, obj.main_nazwa)
        return "-"

    main_zrodlo_link.short_description = "Źródło główne"

    def duplicate_zrodlo_link(self, obj):
        if obj.duplicate_zrodlo_id:
            url = reverse("admin:bpp_zrodlo_change", args=[obj.duplicate_zrodlo_id])
            return format_html('<a href="{}">{}</a>', url, obj.duplicate_nazwa)
        return "-"

    duplicate_zrodlo_link.short_description = "Duplikat"

    def has_add_permission(self, request):
        return False
