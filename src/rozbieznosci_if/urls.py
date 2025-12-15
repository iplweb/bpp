from django.urls import path

from rozbieznosci_if.views import (
    RozbieznosciExportView,
    RozbieznosciView,
    TaskStatusView,
    UstawWszystkieView,
)

app_name = "rozbieznosci_if"

urlpatterns = [
    path("index/", RozbieznosciView.as_view(), name="index"),
    path("export/", RozbieznosciExportView.as_view(), name="export"),
    path("ustaw-wszystkie/", UstawWszystkieView.as_view(), name="ustaw_wszystkie"),
    path(
        "task-status/<str:task_id>/",
        TaskStatusView.as_view(),
        name="task_status",
    ),
]
