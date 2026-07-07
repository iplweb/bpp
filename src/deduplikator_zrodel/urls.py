from django.urls import path

from . import views

app_name = "deduplikator_zrodel"

urlpatterns = [
    path("", views.duplicate_sources_view, name="duplicate_sources"),
    path("skanuj/", views.start_scan, name="start_scan"),
    path("mark-non-duplicate/", views.mark_non_duplicate, name="mark_non_duplicate"),
    path("ignore-source/", views.ignore_source, name="ignore_source"),
    path("skip-candidate/", views.skip_candidate, name="skip_candidate"),
    path("unskip-candidate/", views.unskip_candidate, name="unskip_candidate"),
    path("reset-skipped/", views.reset_skipped, name="reset_skipped"),
    path(
        "download-duplicates-xlsx/",
        views.download_duplicates_xlsx,
        name="download_duplicates_xlsx",
    ),
]
