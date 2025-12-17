from django.urls import path

from pbn_wysylka_oswiadczen.views import (
    CancelTaskView,
    ExcelExportView,
    LogDetailView,
    LogListView,
    PbnWysylkaOswiadczenMainView,
    PublicationListView,
    StartTaskView,
    TaskStatusPartialView,
    TaskStatusView,
)

app_name = "pbn_wysylka_oswiadczen"

urlpatterns = [
    path("", PbnWysylkaOswiadczenMainView.as_view(), name="main"),
    path("publications/", PublicationListView.as_view(), name="publications"),
    path("status/", TaskStatusView.as_view(), name="status"),
    path("status-partial/", TaskStatusPartialView.as_view(), name="status-partial"),
    path("start/", StartTaskView.as_view(), name="start"),
    path("cancel/", CancelTaskView.as_view(), name="cancel"),
    path("export-excel/", ExcelExportView.as_view(), name="export-excel"),
    path("logs/", LogListView.as_view(), name="logs"),
    path("logs/<int:pk>/", LogDetailView.as_view(), name="log-detail"),
]
