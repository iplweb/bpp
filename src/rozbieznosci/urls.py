from django.urls import path

from rozbieznosci.views import (
    RozbieznosciExportView,
    RozbieznosciView,
    TaskStatusView,
    UstawWszystkieView,
)

app_name = "rozbieznosci"

urlpatterns = [
    path("<slug:metryka>/", RozbieznosciView.as_view(), name="index"),
    path(
        "<slug:metryka>/export/",
        RozbieznosciExportView.as_view(),
        name="export",
    ),
    path(
        "<slug:metryka>/ustaw-wszystkie/",
        UstawWszystkieView.as_view(),
        name="ustaw_wszystkie",
    ),
    path(
        "<slug:metryka>/task-status/<str:task_id>/",
        TaskStatusView.as_view(),
        name="task_status",
    ),
]
