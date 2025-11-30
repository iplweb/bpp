"""Admin dashboard views package.

This package provides backward compatibility - all views that were previously
in views.py are re-exported here.
"""

# Base views
from .base import database_stats, recent_logins_view

# Charakter formalny statistics
from .charakter_stats import (
    _get_admin_url_for_charakter,
    _get_charakter_counts,
    charakter_formalny_stats_remaining1,
    charakter_formalny_stats_remaining10,
    charakter_formalny_stats_top90,
)

# Menu tracking
from .menu_tracking import MENU_EMOJI_MAPPING, log_menu_click, menu_clicks_stats

# Time series statistics
from .time_series import (
    cumulative_impact_factor_stats,
    cumulative_points_kbn_stats,
    cumulative_publications_stats,
    day_of_month_activity_stats,
    new_publications_stats,
    weekday_stats,
)

__all__ = [
    # Base views
    "recent_logins_view",
    "database_stats",
    # Time series statistics
    "weekday_stats",
    "day_of_month_activity_stats",
    "new_publications_stats",
    "cumulative_publications_stats",
    "cumulative_impact_factor_stats",
    "cumulative_points_kbn_stats",
    # Charakter formalny statistics
    "_get_admin_url_for_charakter",
    "_get_charakter_counts",
    "charakter_formalny_stats_top90",
    "charakter_formalny_stats_remaining10",
    "charakter_formalny_stats_remaining1",
    # Menu tracking
    "MENU_EMOJI_MAPPING",
    "log_menu_click",
    "menu_clicks_stats",
]
