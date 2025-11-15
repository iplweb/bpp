from django.urls import path

from .views import (
    PBNExportQueueCountsView,
    PBNExportQueueDetailView,
    PBNExportQueueListView,
    PBNExportQueueTableView,
    prepare_for_resend,
    resend_all_errors,
    resend_all_waiting,
    resend_to_pbn,
    try_send_to_pbn,
    wake_up_queue,
)

app_name = "pbn_export_queue"

urlpatterns = [
    # Export Queue views
    path("", PBNExportQueueListView.as_view(), name="export-queue-list"),
    path(
        "table/",
        PBNExportQueueTableView.as_view(),
        name="export-queue-table",
    ),
    path(
        "counts/",
        PBNExportQueueCountsView.as_view(),
        name="export-queue-counts",
    ),
    path(
        "<int:pk>/",
        PBNExportQueueDetailView.as_view(),
        name="export-queue-detail",
    ),
    path("<int:pk>/resend/", resend_to_pbn, name="export-queue-resend"),
    path(
        "<int:pk>/prepare-resend/",
        prepare_for_resend,
        name="export-queue-prepare-resend",
    ),
    path("<int:pk>/try-send/", try_send_to_pbn, name="export-queue-try-send"),
    path(
        "resend-all-errors/",
        resend_all_errors,
        name="export-queue-resend-all-errors",
    ),
    path(
        "resend-all-waiting/",
        resend_all_waiting,
        name="export-queue-resend-all-waiting",
    ),
    path(
        "wake-up/",
        wake_up_queue,
        name="export-queue-wake-up",
    ),
]
