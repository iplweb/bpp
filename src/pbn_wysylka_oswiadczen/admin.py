from django.contrib import admin

from pbn_wysylka_oswiadczen.models import PbnWysylkaLog, PbnWysylkaOswiadczenTask


class PbnWysylkaLogInline(admin.TabularInline):
    model = PbnWysylkaLog
    extra = 0
    readonly_fields = [
        "content_type",
        "object_id",
        "pbn_uid",
        "status",
        "created_at",
        "error_message",
        "retry_count",
    ]
    fields = readonly_fields
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PbnWysylkaOswiadczenTask)
class PbnWysylkaOswiadczenTaskAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "status",
        "rok_od",
        "rok_do",
        "progress_display",
        "success_count",
        "error_count",
        "skipped_count",
        "created_at",
    ]
    list_filter = ["status", "rok_od", "rok_do", "created_at"]
    search_fields = ["user__username", "error_message"]
    readonly_fields = [
        "user",
        "status",
        "created_at",
        "started_at",
        "completed_at",
        "last_updated",
        "total_publications",
        "processed_publications",
        "current_publication",
        "success_count",
        "error_count",
        "skipped_count",
        "celery_task_id",
        "error_message",
    ]
    ordering = ["-created_at"]
    inlines = [PbnWysylkaLogInline]

    def progress_display(self, obj):
        return f"{obj.processed_publications}/{obj.total_publications} ({obj.progress_percent}%)"

    progress_display.short_description = "Postep"

    def has_add_permission(self, request):
        return False


@admin.register(PbnWysylkaLog)
class PbnWysylkaLogAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "task",
        "pbn_uid",
        "status",
        "retry_count",
        "created_at",
    ]
    list_filter = ["status", "task", "created_at"]
    search_fields = ["pbn_uid", "error_message"]
    readonly_fields = [
        "task",
        "content_type",
        "object_id",
        "pbn_uid",
        "status",
        "created_at",
        "json_sent",
        "json_response",
        "error_message",
        "retry_count",
    ]
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        return False
