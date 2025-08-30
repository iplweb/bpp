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
    path("delete-author/", views.delete_author, name="delete_author"),
    path("scal-autorow/", views.scal_autorow_view, name="scal_autorow"),
    path(
        "download-duplicates-xlsx/",
        views.download_duplicates_xlsx,
        name="download_duplicates_xlsx",
    ),
]
