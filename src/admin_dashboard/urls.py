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
    path(
        "cumulative-publications-stats/",
        views.cumulative_publications_stats,
        name="cumulative_publications_stats",
    ),
    path(
        "cumulative-impact-factor-stats/",
        views.cumulative_impact_factor_stats,
        name="cumulative_impact_factor_stats",
    ),
    path(
        "cumulative-points-kbn-stats/",
        views.cumulative_points_kbn_stats,
        name="cumulative_points_kbn_stats",
    ),
    path(
        "charakter-formalny-stats-top90/",
        views.charakter_formalny_stats_top90,
        name="charakter_formalny_stats_top90",
    ),
    path(
        "charakter-formalny-stats-remaining10/",
        views.charakter_formalny_stats_remaining10,
        name="charakter_formalny_stats_remaining10",
    ),
    path(
        "charakter-formalny-stats-remaining1/",
        views.charakter_formalny_stats_remaining1,
        name="charakter_formalny_stats_remaining1",
    ),
    path("database-stats/", views.database_stats, name="database_stats"),
]
