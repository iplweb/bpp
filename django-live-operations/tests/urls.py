"""Test URL configuration — concrete DemoOp views under live_operations namespace."""
from django.urls import path

from tests.views import (
    CancelDemoOpView,
    CreateDemoOpView,
    ListDemoOpView,
    LiveDemoOpView,
    RestartDemoOpView,
)

app_name = "live_operations"

urlpatterns = [
    path("", ListDemoOpView.as_view(), name="index"),
    path("new/", CreateDemoOpView.as_view(), name="new"),
    path("<uuid:pk>/", LiveDemoOpView.as_view(), name="live"),
    path("<uuid:pk>/cancel/", CancelDemoOpView.as_view(), name="cancel"),
    path("<uuid:pk>/restart/", RestartDemoOpView.as_view(), name="restart"),
]
