from django.urls import path

from . import views

app_name = "admin_dashboard"

urlpatterns = [
    path("recent-logins/", views.recent_logins_view, name="recent_logins"),
    path("weekday-stats/", views.weekday_stats, name="weekday_stats"),
    path(
        "day-of-month-activity-stats/",
        views.day_of_month_activity_stats,
        name="day_of_month_activity_stats",
    ),
    path(
        "new-publications-stats/",
        views.new_publications_stats,
        name="new_publications_stats",
    ),
    path("database-stats/", views.database_stats, name="database_stats"),
]
