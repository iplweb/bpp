from django.contrib import admin

from bpp.admin.core import DynamicAdminFilterMixin
from pbn_downloader_app.models import (
    PbnDownloadTask,
    PbnInstitutionPeopleTask,
    PbnJournalsDownloadTask,
)


@admin.register(PbnDownloadTask)
class PbnDownloadTaskAdmin(DynamicAdminFilterMixin, admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "status",
        "progress_percentage",
        "started_at",
        "completed_at",
        "last_updated",
    ]
    list_filter = ["status", "started_at"]
    readonly_fields = [
        "started_at",
        "completed_at",
        "last_updated",
    ]
    search_fields = ["user__username", "error_message"]
    ordering = ["-started_at"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("user", "status", "started_at", "completed_at")},
        ),
        (
            "Progress Information",
            {
                "fields": (
                    "current_step",
                    "progress_percentage",
                    "publications_processed",
                    "total_publications",
                    "statements_processed",
                    "total_statements",
                    "last_updated",
                )
            },
        ),
        (
            "Error Information",
            {
                "fields": ("error_message",),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(PbnInstitutionPeopleTask)
class PbnInstitutionPeopleTaskAdmin(DynamicAdminFilterMixin, admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "status",
        "progress_percentage",
        "started_at",
        "completed_at",
        "last_updated",
    ]
    list_filter = ["status", "started_at"]
    readonly_fields = [
        "started_at",
        "completed_at",
        "last_updated",
    ]
    search_fields = ["user__username", "error_message"]
    ordering = ["-started_at"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("user", "status", "started_at", "completed_at")},
        ),
        (
            "Progress Information",
            {
                "fields": (
                    "current_step",
                    "progress_percentage",
                    "people_processed",
                    "total_people",
                    "last_updated",
                )
            },
        ),
        (
            "Error Information",
            {
                "fields": ("error_message",),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(PbnJournalsDownloadTask)
class PbnJournalsDownloadTaskAdmin(DynamicAdminFilterMixin, admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "status",
        "progress_percentage",
        "started_at",
        "completed_at",
        "last_updated",
    ]
    list_filter = ["status", "started_at"]
    readonly_fields = [
        "started_at",
        "completed_at",
        "last_updated",
    ]
    search_fields = ["user__username", "error_message"]
    ordering = ["-started_at"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("user", "status", "started_at", "completed_at")},
        ),
        (
            "Progress Information",
            {
                "fields": (
                    "current_step",
                    "progress_percentage",
                    "journals_processed",
                    "total_journals",
                    "zrodla_integrated",
                    "last_updated",
                )
            },
        ),
        (
            "Error Information",
            {
                "fields": ("error_message",),
                "classes": ("collapse",),
            },
        ),
    )
