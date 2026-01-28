from django.urls import path

from . import views

app_name = "deduplikator_publikacji"

urlpatterns = [
    path(
        "duplicate-publications/",
        views.duplicate_publications_view,
        name="duplicate_publications",
    ),
    path("start-scan/", views.start_scan_view, name="start_scan"),
    path("cancel-scan/", views.cancel_scan_view, name="cancel_scan"),
    path("scan-status/<int:scan_id>/", views.scan_status_view, name="scan_status"),
    path(
        "mark-not-duplicate/",
        views.mark_not_duplicate_view,
        name="mark_not_duplicate",
    ),
    path(
        "mark-confirmed-duplicate/",
        views.mark_confirmed_duplicate_view,
        name="mark_confirmed_duplicate",
    ),
]
