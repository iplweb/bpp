"""Admin interface for PBN import models"""

from django.contrib import admin
from django.utils.html import format_html

from .models import ImportLog, ImportSession, ImportStatistics, ImportStep


@admin.register(ImportSession)
class ImportSessionAdmin(admin.ModelAdmin):
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

    def status_badge(self, obj):
        colors = {
            "pending": "#ffc107",
            "running": "#17a2b8",
            "paused": "#6c757d",
            "completed": "#28a745",
            "failed": "#dc3545",
            "cancelled": "#6c757d",
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            colors.get(obj.status, "#6c757d"),
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def progress_bar(self, obj):
        progress = obj.overall_progress
        color = "#28a745" if progress == 100 else "#17a2b8"
        return format_html(
            '<div style="width: 100px; background-color: #e9ecef; '
            'border-radius: 3px; overflow: hidden;">'
            '<div style="width: {}%; background-color: {}; height: 20px; '
            'text-align: center; color: white; line-height: 20px;">'
            "{}%</div></div>",
            progress,
            color,
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
                '<div style="color: #dc3545;"><strong>Message:</strong><br>{}</div>'
                '<details style="margin-top: 10px;"><summary>Traceback</summary>'
                '<pre style="font-size: 0.9em;">{}</pre></details>',
                obj.error_message,
                obj.error_traceback or "No traceback available",
            )
        return "-"

    error_display.short_description = "Error Details"

    def has_add_permission(self, request):
        # Don't allow manual creation through admin
        return False


@admin.register(ImportLog)
class ImportLogAdmin(admin.ModelAdmin):
    list_display = [
        "timestamp",
        "session_link",
        "level_badge",
        "step",
        "message_truncated",
    ]
    list_filter = ["level", "step", "timestamp"]
    search_fields = ["message", "step"]
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
        colors = {
            "debug": "#6c757d",
            "info": "#17a2b8",
            "warning": "#ffc107",
            "error": "#dc3545",
            "success": "#28a745",
            "critical": "#721c24",
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 0.9em;">{}</span>',
            colors.get(obj.level, "#6c757d"),
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

            return format_html("<pre>{}</pre>", json.dumps(obj.details, indent=2))
        return "-"

    details_display.short_description = "Details"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ImportStep)
class ImportStepAdmin(admin.ModelAdmin):
    list_display = [
        "order",
        "icon_display",
        "display_name",
        "name",
        "is_optional",
        "estimated_duration_display",
    ]
    list_display_links = ["display_name"]
    list_editable = ["order", "is_optional"]
    ordering = ["order"]

    def icon_display(self, obj):
        return format_html('<span class="{}"></span>', obj.icon_class)

    icon_display.short_description = "Icon"

    def estimated_duration_display(self, obj):
        if obj.estimated_duration >= 60:
            minutes = obj.estimated_duration // 60
            seconds = obj.estimated_duration % 60
            if seconds:
                return f"{minutes}m {seconds}s"
            return f"{minutes}m"
        return f"{obj.estimated_duration}s"

    estimated_duration_display.short_description = "Est. Duration"


@admin.register(ImportStatistics)
class ImportStatisticsAdmin(admin.ModelAdmin):
    list_display = ["session", "total_imported", "total_failed", "api_performance"]
    readonly_fields = [
        "session",
        "institutions_imported",
        "authors_imported",
        "publications_imported",
        "journals_imported",
        "publishers_imported",
        "conferences_imported",
        "statements_imported",
        "institutions_failed",
        "authors_failed",
        "publications_failed",
        "total_api_calls",
        "api_performance",
        "coffee_breaks_display",
    ]

    fieldsets = (
        ("Session", {"fields": ("session",)}),
        (
            "Import Statistics",
            {
                "fields": (
                    "institutions_imported",
                    "authors_imported",
                    "publications_imported",
                    "journals_imported",
                    "publishers_imported",
                    "conferences_imported",
                    "statements_imported",
                )
            },
        ),
        (
            "Error Statistics",
            {
                "fields": (
                    "institutions_failed",
                    "authors_failed",
                    "publications_failed",
                )
            },
        ),
        ("Performance", {"fields": ("total_api_calls", "api_performance")}),
        (
            "Fun Stats",
            {
                "fields": ("coffee_breaks_display", "motivational_messages_shown"),
                "classes": ("collapse",),
            },
        ),
    )

    def total_imported(self, obj):
        return (
            obj.institutions_imported
            + obj.authors_imported
            + obj.publications_imported
            + obj.journals_imported
            + obj.publishers_imported
            + obj.conferences_imported
            + obj.statements_imported
        )

    total_imported.short_description = "Total Imported"

    def total_failed(self, obj):
        return obj.institutions_failed + obj.authors_failed + obj.publications_failed

    total_failed.short_description = "Total Failed"

    def api_performance(self, obj):
        if obj.total_api_calls > 0:
            avg_time = obj.total_api_time / obj.total_api_calls
            return f"{obj.total_api_calls} calls, {avg_time:.2f}s avg"
        return "No API calls"

    api_performance.short_description = "API Performance"

    def coffee_breaks_display(self, obj):
        if obj.coffee_breaks_recommended > 0:
            return format_html("☕ × {} (recommended)", obj.coffee_breaks_recommended)
        return "None needed!"

    coffee_breaks_display.short_description = "Coffee Breaks"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
