from django.urls import path

from . import views

app_name = "komparator_pbn"

urlpatterns = [
    path("", views.KomparatorMainView.as_view(), name="main"),
    path(
        "bpp-missing-in-pbn/",
        views.BPPMissingInPBNView.as_view(),
        name="bpp_missing_in_pbn",
    ),
    path(
        "pbn-missing-in-bpp/",
        views.PBNMissingInBPPView.as_view(),
        name="pbn_missing_in_bpp",
    ),
    # API endpoints
    path(
        "api/start-download/",
        views.StartPbnDownloadView.as_view(),
        name="start_download",
    ),
    path("api/task-status/", views.TaskStatusView.as_view(), name="task_status"),
    path("api/retry-task/", views.RetryTaskView.as_view(), name="retry_task"),
]
