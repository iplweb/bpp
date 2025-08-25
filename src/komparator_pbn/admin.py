from .models import PbnDownloadTask

from django.contrib import admin


@admin.register(PbnDownloadTask)
class PbnDownloadTaskAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "status",
        "progress_percentage",
        "current_step",
        "started_at",
        "completed_at",
    ]
    list_filter = ["status", "started_at"]
    readonly_fields = ["started_at", "completed_at", "last_updated"]
    search_fields = ["user__username", "current_step"]
    ordering = ["-started_at"]

    fieldsets = [
        (
            "Task Information",
            {
                "fields": [
                    "user",
                    "status",
                    "started_at",
                    "completed_at",
                    "last_updated",
                ]
            },
        ),
        (
            "Progress Information",
            {
                "fields": [
                    "current_step",
                    "progress_percentage",
                    "publications_processed",
                    "statements_processed",
                    "total_publications",
                    "total_statements",
                ]
            },
        ),
        ("Error Information", {"fields": ["error_message"], "classes": ["collapse"]}),
    ]
