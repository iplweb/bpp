"""Admin interface for PBN import models"""

import html

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from bpp.admin.core import DynamicAdminFilterMixin

from .models import (
    ImportInconsistency,
    ImportLog,
    ImportSession,
)


@admin.register(ImportSession)
class ImportSessionAdmin(DynamicAdminFilterMixin, admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "status_badge",
        "progress_bar",
        "current_step_display",
        "started_at",
        "duration_display",
    ]
    list_filter = ["status", "started_at", "completed_at"]
    search_fields = ["user__username", "user__email", "current_step"]
    list_select_related = ["user"]
    readonly_fields = [
        "started_at",
        "completed_at",
        "duration_display",
        "overall_progress_display",
        "progress_data_display",
        "error_display",
    ]

    fieldsets = (
        (
            "Session Information",
            {
                "fields": (
                    "user",
                    "status",
                    "started_at",
                    "completed_at",
                    "duration_display",
                )
            },
        ),
        (
            "Progress",
            {
                "fields": (
                    "current_step",
                    "current_step_progress",
                    "overall_progress_display",
                    "total_steps",
                    "completed_steps",
                )
            },
        ),
        ("Configuration", {"fields": ("config",), "classes": ("collapse",)}),
        (
            "Progress Data",
            {"fields": ("progress_data_display",), "classes": ("collapse",)},
        ),
        ("Errors", {"fields": ("error_display",), "classes": ("collapse",)}),
    )

    class Media:
        css = {
            "all": ["pbn_import/css/admin.css"],
        }

    def status_badge(self, obj):
        status_class = f"pbn-status-badge--{obj.status}"
        return format_html(
            '<span class="pbn-status-badge {}">{}</span>',
            status_class,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def progress_bar(self, obj):
        progress = obj.overall_progress
        fill_class = (
            "pbn-progress-bar__fill--complete"
            if progress == 100
            else "pbn-progress-bar__fill--in-progress"
        )
        return format_html(
            '<div class="pbn-progress-bar">'
            '<div class="pbn-progress-bar__fill {}" style="width: {}%">'
            "{}%</div></div>",
            fill_class,
            progress,
            progress,
        )

    progress_bar.short_description = "Progress"

    def current_step_display(self, obj):
        if obj.current_step:
            return f"{obj.current_step} ({obj.current_step_progress}%)"
        return "-"

    current_step_display.short_description = "Current Step"

    def duration_display(self, obj):
        if obj.duration:
            total_seconds = int(obj.duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60

            if hours:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return "-"

    duration_display.short_description = "Duration"

    def overall_progress_display(self, obj):
        return self.progress_bar(obj)

    overall_progress_display.short_description = "Overall Progress"

    def progress_data_display(self, obj):
        if obj.progress_data:
            import json

            return format_html("<pre>{}</pre>", json.dumps(obj.progress_data, indent=2))
        return "-"

    progress_data_display.short_description = "Progress Data"

    def error_display(self, obj):
        if obj.error_message:
            return format_html(
                '<div class="pbn-error-display">'
                '<div class="pbn-error-display__message">'
                "<strong>Message:</strong><br>{}</div>"
                '<details class="pbn-error-display__traceback">'
                "<summary>Traceback</summary>"
                '<pre class="pbn-error-display__traceback-content">{}</pre>'
                "</details></div>",
                obj.error_message,
                obj.error_traceback or "No traceback available",
            )
        return "-"

    error_display.short_description = "Error Details"

    def has_add_permission(self, request):
        # Don't allow manual creation through admin
        return False


@admin.register(ImportLog)
class ImportLogAdmin(DynamicAdminFilterMixin, admin.ModelAdmin):
    list_display = [
        "timestamp",
        "session_link",
        "level_badge",
        "step",
        "message_truncated",
    ]
    list_filter = ["level", "step", "timestamp"]
    search_fields = ["message", "step"]
    list_select_related = ["session"]
    readonly_fields = [
        "timestamp",
        "session",
        "level",
        "step",
        "message",
        "details_display",
    ]
    date_hierarchy = "timestamp"

    def session_link(self, obj):
        return format_html(
            '<a href="/admin/pbn_import/importsession/{}/change/">Session #{}</a>',
            obj.session.id,
            obj.session.id,
        )

    session_link.short_description = "Session"

    def level_badge(self, obj):
        level_class = f"pbn-level-badge--{obj.level}"
        return format_html(
            '<span class="pbn-level-badge {}">{}</span>',
            level_class,
            obj.get_level_display(),
        )

    level_badge.short_description = "Level"

    def message_truncated(self, obj):
        if len(obj.message) > 100:
            return obj.message[:100] + "..."
        return obj.message

    message_truncated.short_description = "Message"

    def details_display(self, obj):
        if obj.details:
            import json

            formatted = json.dumps(
                obj.details, indent=2, sort_keys=True, ensure_ascii=False
            )
            # Zamień escaped newlines na rzeczywiste nowe linie dla czytelności
            formatted = formatted.replace("\\n", "\n")
            # Bezpieczne HTML escaping
            escaped = html.escape(formatted)
            return mark_safe(
                f'<pre style="white-space: pre-wrap; max-width: 800px;">{escaped}</pre>'
            )
        return "-"

    details_display.short_description = "Details"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ImportInconsistency)
class ImportInconsistencyAdmin(DynamicAdminFilterMixin, admin.ModelAdmin):
    list_display = [
        "timestamp",
        "session_link",
        "type_badge",
        "resolved_badge",
        "pbn_author_name",
        "bpp_author_name",
        "message_truncated",
    ]
    list_filter = [
        "session",
        "inconsistency_type",
        "resolved",
        "timestamp",
    ]
    search_fields = [
        "message",
        "action_taken",
        "pbn_publication_title",
        "pbn_author_name",
        "pbn_discipline",
        "bpp_publication_title",
        "bpp_author_name",
    ]
    readonly_fields = [
        "timestamp",
        "session",
        "inconsistency_type",
        "pbn_publication_id",
        "pbn_publication_title",
        "pbn_author_id",
        "pbn_author_name",
        "pbn_discipline",
        "bpp_publication_id",
        "bpp_publication_content_type",
        "bpp_publication_title",
        "bpp_author_id",
        "bpp_author_name",
        "message",
        "action_taken",
    ]
    date_hierarchy = "timestamp"
    list_per_page = 50
    list_select_related = ["session", "bpp_publication_content_type"]

    fieldsets = (
        (
            "Informacje podstawowe",
            {
                "fields": (
                    "session",
                    "timestamp",
                    "inconsistency_type",
                    "resolved",
                    "resolved_at",
                )
            },
        ),
        (
            "Dane PBN",
            {
                "fields": (
                    "pbn_publication_id",
                    "pbn_publication_title",
                    "pbn_author_id",
                    "pbn_author_name",
                    "pbn_discipline",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Dane BPP",
            {
                "fields": (
                    "bpp_publication_id",
                    "bpp_publication_content_type",
                    "bpp_publication_title",
                    "bpp_author_id",
                    "bpp_author_name",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Opis problemu", {"fields": ("message", "action_taken")}),
    )

    def session_link(self, obj):
        return format_html(
            '<a href="/admin/pbn_import/importsession/{}/change/">Session #{}</a>',
            obj.session.id,
            obj.session.id,
        )

    session_link.short_description = "Sesja"

    def type_badge(self, obj):
        type_colors = {
            "author_not_found": "pbn-level-badge--warning",
            "author_auto_fixed": "pbn-level-badge--info",
            "author_needs_manual_fix": "pbn-level-badge--error",
            "no_override_without_disciplines": "pbn-level-badge--warning",
            "publication_not_found": "pbn-level-badge--error",
            "author_not_in_bpp": "pbn-level-badge--error",
        }
        badge_class = type_colors.get(obj.inconsistency_type, "pbn-level-badge--info")
        return format_html(
            '<span class="pbn-level-badge {}">{}</span>',
            badge_class,
            obj.get_inconsistency_type_display(),
        )

    type_badge.short_description = "Typ"

    def resolved_badge(self, obj):
        if obj.resolved:
            return format_html(
                '<span class="pbn-status-badge pbn-status-badge--completed">Tak</span>'
            )
        return format_html(
            '<span class="pbn-status-badge pbn-status-badge--pending">Nie</span>'
        )

    resolved_badge.short_description = "Rozwiązano"

    def message_truncated(self, obj):
        if len(obj.message) > 80:
            return obj.message[:80] + "..."
        return obj.message

    message_truncated.short_description = "Opis"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        # Pozwól na usuwanie - może być potrzebne do czyszczenia
        return True
