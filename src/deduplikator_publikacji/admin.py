from django.contrib import admin

from .models import PublicationDuplicateCandidate, PublicationDuplicateScanRun


@admin.register(PublicationDuplicateScanRun)
class PublicationDuplicateScanRunAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.is_superuser

    list_display = [
        "pk",
        "status",
        "year_from",
        "year_to",
        "started_at",
        "finished_at",
        "publications_scanned",
        "duplicates_found",
        "created_by",
    ]
    list_filter = ["status", "year_from", "year_to"]
    readonly_fields = [
        "started_at",
        "finished_at",
        "publications_scanned",
        "total_publications_to_scan",
        "duplicates_found",
        "celery_task_id",
        "error_message",
    ]
    ordering = ["-started_at"]

    def get_actions(self, request):
        # Bulk delete would bypass has_delete_permission(obj) and remove
        # (CASCADE) the "not a duplicate" decisions of the deleted scans.
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def has_delete_permission(self, request, obj=None):
        # A scan holding "not a duplicate" decisions must stay: deleting it
        # would delete the decisions and the rejected pairs would return.
        if (
            obj is not None
            and obj.candidates.filter(
                status=PublicationDuplicateCandidate.Status.NOT_DUPLICATE
            ).exists()
        ):
            return False
        return super().has_delete_permission(request, obj)


@admin.register(PublicationDuplicateCandidate)
class PublicationDuplicateCandidateAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.is_superuser

    list_display = [
        "pk",
        "original_title_short",
        "duplicate_title_short",
        "similarity_score",
        "status",
        "original_type",
        "duplicate_type",
        "reviewed_by",
    ]
    list_filter = ["status", "original_type", "duplicate_type", "scan_run"]
    search_fields = ["original_title", "duplicate_title"]
    readonly_fields = [
        "scan_run",
        "original_content_type",
        "original_object_id",
        "duplicate_content_type",
        "duplicate_object_id",
        "similarity_score",
        "match_reasons",
        "original_title",
        "duplicate_title",
        "original_year",
        "duplicate_year",
        "original_type",
        "duplicate_type",
        "created_at",
    ]
    ordering = ["-similarity_score"]

    def original_title_short(self, obj):
        return (
            obj.original_title[:60] + "..."
            if len(obj.original_title) > 60
            else obj.original_title
        )

    original_title_short.short_description = "Oryginał"

    def duplicate_title_short(self, obj):
        return (
            obj.duplicate_title[:60] + "..."
            if len(obj.duplicate_title) > 60
            else obj.duplicate_title
        )

    duplicate_title_short.short_description = "Duplikat"
