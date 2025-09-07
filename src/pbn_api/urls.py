# https://publikacje.up.lublin.pl/pbn_api/callback?ott=dc37f06a-30bd-445a-80bd-199745f65d62


from django.urls import path

from .views import (
    PBNExportQueueDetailView,
    PBNExportQueueListView,
    PBNExportQueueTableView,
    TokenLandingPage,
    TokenRedirectPage,
    prepare_for_resend,
    resend_to_pbn,
    try_send_to_pbn,
)

app_name = "pbn_api"

urlpatterns = [
    path("callback", TokenLandingPage.as_view(), name="callback"),
    path("authorize", TokenRedirectPage.as_view(), name="authorize"),
    # Export Queue views
    path("export-queue/", PBNExportQueueListView.as_view(), name="export-queue-list"),
    path(
        "export-queue/table/",
        PBNExportQueueTableView.as_view(),
        name="export-queue-table",
    ),
    path(
        "export-queue/<int:pk>/",
        PBNExportQueueDetailView.as_view(),
        name="export-queue-detail",
    ),
    path("export-queue/<int:pk>/resend/", resend_to_pbn, name="export-queue-resend"),
    path(
        "export-queue/<int:pk>/prepare-resend/",
        prepare_for_resend,
        name="export-queue-prepare-resend",
    ),
    path(
        "export-queue/<int:pk>/try-send/", try_send_to_pbn, name="export-queue-try-send"
    ),
]
