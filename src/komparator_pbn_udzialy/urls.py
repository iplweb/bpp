from django.urls import path

from komparator_pbn_udzialy.views import (
    RebuildDiscrepanciesView,
    RozbieznoscDyscyplinPBNDetailView,
    RozbieznoscDyscyplinPBNListView,
    TaskStatusAPIView,
    TaskStatusView,
)

app_name = "komparator_pbn_udzialy"

urlpatterns = [
    path(
        "",
        RozbieznoscDyscyplinPBNListView.as_view(),
        name="list",
    ),
    path(
        "<int:pk>/",
        RozbieznoscDyscyplinPBNDetailView.as_view(),
        name="detail",
    ),
    path(
        "rebuild/",
        RebuildDiscrepanciesView.as_view(),
        name="rebuild",
    ),
    path(
        "task/<str:task_id>/",
        TaskStatusView.as_view(),
        name="task_status",
    ),
    path(
        "api/task/<str:task_id>/status/",
        TaskStatusAPIView.as_view(),
        name="task_status_api",
    ),
]
