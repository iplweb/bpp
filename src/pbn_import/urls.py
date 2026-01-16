"""URL configuration for PBN import"""

from django.urls import path

from . import views

app_name = "pbn_import"

urlpatterns = [
    # Main dashboard
    path("", views.ImportDashboardView.as_view(), name="dashboard"),
    # Import control
    path("start/", views.StartImportView.as_view(), name="start"),
    path(
        "session/<int:pk>/",
        views.ImportSessionDetailView.as_view(),
        name="session_detail",
    ),
    path("session/<int:pk>/cancel/", views.CancelImportView.as_view(), name="cancel"),
    # HTMX endpoints
    path(
        "session/<int:pk>/progress/",
        views.ImportProgressView.as_view(),
        name="progress",
    ),
    path("session/<int:pk>/logs/", views.ImportLogStreamView.as_view(), name="logs"),
    path("session/<int:pk>/stats/", views.ImportStatisticsView.as_view(), name="stats"),
    path(
        "session/<int:pk>/all-logs/",
        views.ImportAllLogsView.as_view(),
        name="all_logs",
    ),
    path(
        "session/<int:pk>/error-logs/",
        views.ImportErrorLogsView.as_view(),
        name="error_logs",
    ),
    path(
        "sessions/active/", views.ActiveSessionsView.as_view(), name="active_sessions"
    ),
    # Configuration presets
    path("presets/", views.ImportPresetsView.as_view(), name="presets"),
    path("presets/save/", views.SavePresetView.as_view(), name="save_preset"),
]
