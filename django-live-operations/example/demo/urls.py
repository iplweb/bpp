from django.urls import path

from demo.views import (
    CancelDemoImportView,
    CreateDemoImportView,
    ListDemoImportView,
    LiveDemoImportView,
    RestartDemoImportView,
)

app_name = "live_operations"

urlpatterns = [
    path("", ListDemoImportView.as_view(), name="index"),
    path("new/", CreateDemoImportView.as_view(), name="new"),
    path("<uuid:pk>/", LiveDemoImportView.as_view(), name="live"),
    path("<uuid:pk>/cancel/", CancelDemoImportView.as_view(), name="cancel"),
    path("<uuid:pk>/restart/", RestartDemoImportView.as_view(), name="restart"),
]
