from django.urls import path

from rozbieznosci_pk.views import (
    RozbieznosciPkExportView,
    RozbieznosciPkView,
    TaskStatusPkView,
    UstawWszystkiePkView,
)

app_name = "rozbieznosci_pk"

urlpatterns = [
    path("index/", RozbieznosciPkView.as_view(), name="index"),
    path("export/", RozbieznosciPkExportView.as_view(), name="export"),
    path("ustaw-wszystkie/", UstawWszystkiePkView.as_view(), name="ustaw_wszystkie"),
    path(
        "task-status/<str:task_id>/",
        TaskStatusPkView.as_view(),
        name="task_status",
    ),
]
