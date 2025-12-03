from django.urls import path

from . import views

app_name = "deduplikator_autorow"

urlpatterns = [
    path("duplicate-authors/", views.duplicate_authors_view, name="duplicate_authors"),
    path("mark-non-duplicate/", views.mark_non_duplicate, name="mark_non_duplicate"),
    path(
        "reset-skipped-authors/",
        views.reset_skipped_authors,
        name="reset_skipped_authors",
    ),
    path(
        "reset-not-duplicates/", views.reset_not_duplicates, name="reset_not_duplicates"
    ),
    path("ignore-author/", views.ignore_author, name="ignore_author"),
    path(
        "reset-ignored-authors/",
        views.reset_ignored_authors,
        name="reset_ignored_authors",
    ),
    path("delete-author/", views.delete_author, name="delete_author"),
    path("scal-autorow/", views.scal_autorow_view, name="scal_autorow"),
    path(
        "download-duplicates-xlsx/",
        views.download_duplicates_xlsx,
        name="download_duplicates_xlsx",
    ),
    # Scan management endpoints
    path("start-scan/", views.start_scan_view, name="start_scan"),
    path("cancel-scan/", views.cancel_scan_view, name="cancel_scan"),
    path("scan-status/<int:scan_id>/", views.scan_status_view, name="scan_status"),
    path(
        "mark-candidate-not-duplicate/",
        views.mark_candidate_not_duplicate,
        name="mark_candidate_not_duplicate",
    ),
]
